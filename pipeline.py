import re
import uuid
import time
import logging
from datetime import datetime
from openai import OpenAI
from duckduckgo_search import DDGS
from bs4 import BeautifulSoup
import httpx

from config import OPENAI_API_KEY, OPENAI_BASE_URL, s3_client, S3_BUCKET_NAME, REPORTS_DIR
from models import SessionLocal, Competitor, CompetitorChunk

logger = logging.getLogger(__name__)

# ==================== БАЗА ДАННЫХ ====================
def clear_db():
    db = SessionLocal()
    try:
        db.query(CompetitorChunk).delete()
        db.query(Competitor).delete()
        db.commit()
        logger.info("🧹 База данных очищена")
    finally:
        db.close()

# ==================== ПАРСИНГ (EXTRACT) ====================
async def fetch_full_text(url: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
            tag.decompose()
        
        main_content = soup.find('main') or soup.find('article') or soup.body
        if not main_content:
            return ""
        
        text = main_content.get_text(separator=' ', strip=True)
        return text[:10000]
    except Exception as e:
        logger.warning(f"Не удалось загрузить {url}: {e}")
        return ""

def parse_competitors(niche: str, geo: str, max_results: int = 100):
    import asyncio
    query = f"{niche} {geo}"
    logger.info(f"🔍 Поиск в DuckDuckGo: {query}")
    
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if not results:
            logger.warning("DuckDuckGo не вернул результатов")
            return 0

        db = SessionLocal()
        added = 0
        try:
            for r in results:
                url = r.get('href')
                if not url or not url.startswith('http'): continue
                
                exists = db.query(Competitor.id).filter(Competitor.url == url).first()
                if not exists:
                    full_text = asyncio.run(fetch_full_text(url))
                    new_comp = Competitor(
                        url=url, title=r.get('title', ''), description=r.get('body', ''),
                        full_text=full_text, niche=niche, geo=geo, status='parsed'
                    )
                    db.add(new_comp)
                    added += 1
                    if added % 10 == 0:
                        logger.info(f"   🔄 Обработано {added}/{len(results)}")
            db.commit()
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
        logger.info(f"✅ Добавлено {added} сайтов")
        return added
    except Exception as e:
        logger.error(f"Ошибка парсинга: {e}")
        return 0

# ==================== ОЧИСТКА И ЧАНКИНГ (TRANSFORM) ====================
def clean_text_logic(title: str, description: str, geo: str) -> str:
    if not title and not description: return ""
    combined = f"{title or ''}. {description or ''}"
    SEO_PATTERNS = [r'\bвсе\s+\w+\s+(москв[аы]|спб)\b', r'\bв\s+аренду\s+под\s+мероприятие\b',
                    r'\bу\s+метро\s+[\w\s]+', r'\bот\s+\d+\s+руб\b']
    for pattern in SEO_PATTERNS:
        combined = re.sub(pattern, '', combined, flags=re.IGNORECASE)
    combined = re.sub(r'\s\-\s', '. ', combined)
    combined = re.sub(r'\s*\|\s*', '. ', combined)
    combined = re.sub(r'\s{2,}', ' ', combined)
    if geo:
        geo_pattern = re.compile(re.escape(geo), flags=re.IGNORECASE)
        matches = list(geo_pattern.finditer(combined))
        if len(matches) > 1:
            for match in reversed(matches[1:]):
                combined = combined[:match.start()] + combined[match.end():]
    return combined.strip(' .,;-').capitalize()

def clean_all_data():
    db = SessionLocal()
    try:
        rows = db.query(Competitor).filter((Competitor.cleaned == False) | (Competitor.cleaned == None)).all()
        for comp in rows:
            comp.clean_text = clean_text_logic(comp.title, comp.description, comp.geo)
            comp.cleaned = True
        db.commit()
        logger.info(f"🧹 Очищено записей: {len(rows)}")
    finally:
        db.close()

def smart_chunking(text: str, max_length: int = 500) -> list:
    if not text or len(text) <= max_length:
        return [text.strip()] if text else []
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks, current_chunk = [], ""
    for sentence in sentences:
        if len(current_chunk) + len(sentence) + 1 <= max_length:
            current_chunk += (" " if current_chunk else "") + sentence
        else:
            if current_chunk: chunks.append(current_chunk)
            current_chunk = sentence
    if current_chunk: chunks.append(current_chunk)
    return [c.strip() for c in chunks if c.strip()]

def chunk_all_data():
    db = SessionLocal()
    try:
        db.query(CompetitorChunk).delete()
        competitors = db.query(Competitor).filter(Competitor.clean_text.isnot(None)).all()
        total = 0
        for comp in competitors:
            for chunk_text in smart_chunking(comp.clean_text):
                new_chunk = CompetitorChunk(
                    competitor_id=comp.id, chunk_text=chunk_text, chunk_length=len(chunk_text),
                    niche=comp.niche, geo=comp.geo, url=comp.url, title=comp.title
                )
                db.add(new_chunk)
                total += 1
        db.commit()
        logger.info(f"✂️ Создано чанков: {total}")
    finally:
        db.close()

# ==================== ВЕКТОРИЗАЦИЯ И RAG ====================
def get_embedding(text: str) -> list | None:
    try:
        client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL, timeout=httpx.Timeout(30.0, connect=5.0))
        response = client.embeddings.create(input=text[:8000], model="text-embedding-3-small")
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Ошибка эмбеддинга: {e}")
        return None

def vectorize_all():
    db = SessionLocal()
    try:
        chunks = db.query(CompetitorChunk).filter(CompetitorChunk.embedding.is_(None)).all()
        logger.info(f"🧠 Векторизация {len(chunks)} чанков...")
        for i, chunk in enumerate(chunks):
            emb = get_embedding(chunk.chunk_text)
            if emb:
                chunk.embedding = emb
            if (i + 1) % 10 == 0:
                db.commit()
                logger.info(f"   🔄 Обработано {i+1}/{len(chunks)}")
            time.sleep(0.2)
        db.commit()
        logger.info("✅ Векторизация завершена")
    finally:
        db.close()

def search_rag_hybrid(query: str, top_k: int = 5) -> list:
    db = SessionLocal()
    try:
        query_vec = get_embedding(query)
        if not query_vec: return []
            
        vector_results = db.query(CompetitorChunk).filter(
            CompetitorChunk.embedding.isnot(None)
        ).order_by(
            CompetitorChunk.embedding.cosine_distance(query_vec)
        ).limit(20).all()
        
        text_results = db.query(CompetitorChunk).filter(
            CompetitorChunk.chunk_text.ilike(f'%{query}%')
        ).limit(20).all()
        
        combined = {}
        for rank, chunk in enumerate(vector_results):
            combined[chunk.chunk_id] = {'chunk': chunk, 'score': 1.0 / (rank + 60)}
        for rank, chunk in enumerate(text_results):
            if chunk.chunk_id in combined:
                combined[chunk.chunk_id]['score'] += 1.0 / (rank + 60)
            else:
                combined[chunk.chunk_id] = {'chunk': chunk, 'score': 1.0 / (rank + 60)}
        
        sorted_candidates = sorted(combined.values(), key=lambda x: x['score'], reverse=True)[:20]
        candidates_for_rerank = [
            {'score': item['score'], 'title': item['chunk'].title, 'url': item['chunk'].url, 'text': item['chunk'].chunk_text}
            for item in sorted_candidates
        ]
        
        # Применяем reranking (если модуль подключен, иначе вернет как есть)
        try:
            from reranker import rerank_results
            final_results = rerank_results(query, candidates_for_rerank, top_k=top_k)
        except ImportError:
            final_results = candidates_for_rerank[:top_k]
            
        return final_results
    finally:
        db.close()

# ==================== ГЕНЕРАЦИЯ И СОХРАНЕНИЕ ====================
def generate_report_structured(query: str, niche: str, geo: str):
    # Упрощенная версия для локального запуска без сложных Pydantic схем, 
    # если вы не создавали schemas.py. Если создавали - используйте её.
    top_results = search_rag_hybrid(query, top_k=5)
    if not top_results:
        return "⚠️ Не найдено релевантной информации в базе данных."

    context_text = "\n".join([f"--- КОНКУРЕНТ {i+1} ---\nНазвание: {r['title']}\nСайт: {r['url']}\nИнформация: {r['text']}\n" for i, r in enumerate(top_results)])
    system_prompt = f"""Ты — профессиональный нейро-аналитик.
Ответь на запрос: {query}
На основе КОНТЕКСТА:
{context_text}
Структура: 1. Конкуренты, 2. Фишки, 3. Чего не хватает."""

    try:
        client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL, timeout=httpx.Timeout(60.0, connect=5.0))
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": query}],
            temperature=0.3
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"❌ Ошибка генерации отчета: {e}"

def save_report(report_text: str, niche: str, geo: str) -> str:
    """🆕 Функция с умным фоллбэком: S3 -> Локальная папка"""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    safe_name = f"{niche}_{geo}_{timestamp}".replace(" ", "_")
    filename = f"Report_{safe_name}_{uuid.uuid4().hex[:6]}.md"
    
    md_content = (f"# 📊 Отчет нейро-аналитика\nНиша: {niche}\nГеография: {geo}\n"
                  f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n---\n\n{report_text}")
    
    # 1. Попытка загрузить в S3 (если переменные в .env раскомментированы)
    if s3_client:
        try:
            s3_client.put_object(Bucket=S3_BUCKET_NAME, Key=filename, Body=md_content.encode('utf-8'), ContentType='text/markdown')
            url = s3_client.generate_presigned_url('get_object', Params={'Bucket': S3_BUCKET_NAME, 'Key': filename}, ExpiresIn=604800)
            logger.info(f"💾 Отчет загружен в S3")
            return url
        except Exception as e:
            logger.warning(f"S3 недоступен ({e}), сохраняем локально...")
            
    # 2. 🆕 Фоллбэк на локальное сохранение (работает всегда, так как папка смонтирована через Docker)
    filepath = REPORTS_DIR / filename
    filepath.write_text(md_content, encoding='utf-8')
    logger.info(f"💾 Отчет сохранен локально: {filepath}")
    return str(filepath)

# ==================== ГЛАВНЫЙ ПАЙПЛАЙН ====================
def run_pipeline(niche: str, geo: str, query: str, clear: bool = False) -> dict:
    from models import init_db
    init_db()
    if clear: clear_db()

    parse_competitors(niche, geo)
    clean_all_data()
    chunk_all_data()
    vectorize_all()
    
    report = generate_report_structured(query, niche, geo)
    filepath = save_report(report, niche, geo)

    return {
        "status": "success", "niche": niche, "geo": geo, "query": query,
        "report": report, "report_url": filepath, "generated_at": datetime.now().isoformat()
    }