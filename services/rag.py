import chromadb
from chromadb.config import Settings
import pypdf
import os
import logging
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class RAGService:
    """Сервис для работы с RAG (Retrieval-Augmented Generation) на основе ChromaDB."""
    
    def __init__(self):
        """
        Инициализирует ChromaDB и создает коллекцию для базы знаний.
        Использует sentence_transformers для создания embeddings.
        """
        # Инициализация ChromaDB с persistent storage
        self.client = chromadb.PersistentClient(
            path="chroma_data",
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # Инициализация модели для embeddings
        logger.info("Загрузка модели sentence_transformers...")
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Создание или получение коллекции
        try:
            self.collection = self.client.get_or_create_collection(
                name="knowledge_base",
                metadata={"description": "База знаний для RAG"}
            )
            logger.info(f"Коллекция 'knowledge_base' инициализирована. Документов: {self.collection.count()}")
        except Exception as e:
            logger.error(f"Ошибка при инициализации коллекции: {e}")
            raise
    
    async def load_knowledge_base(self, folder_path: str):
        """
        Загружает документы из указанной папки в базу знаний.
        
        Args:
            folder_path: Путь к папке с документами (.pdf и .txt файлы)
        """
        if not os.path.exists(folder_path):
            logger.error(f"Папка не найдена: {folder_path}")
            return
        
        documents = []
        metadatas = []
        ids = []
        doc_counter = 0
        
        # Обход всех файлов в папке
        for filename in os.listdir(folder_path):
            file_path = os.path.join(folder_path, filename)
            
            # Пропускаем директории
            if not os.path.isfile(file_path):
                continue
            
            text_content = ""
            
            # Обработка PDF файлов
            if filename.lower().endswith('.pdf'):
                try:
                    with open(file_path, 'rb') as pdf_file:
                        pdf_reader = pypdf.PdfReader(pdf_file)
                        for page in pdf_reader.pages:
                            text_content += page.extract_text() + "\n"
                    logger.info(f"Загружен PDF: {filename}")
                except Exception as e:
                    logger.error(f"Ошибка при чтении PDF {filename}: {e}")
                    continue
            
            # Обработка TXT файлов
            elif filename.lower().endswith('.txt'):
                try:
                    with open(file_path, 'r', encoding='utf-8') as txt_file:
                        text_content = txt_file.read()
                    logger.info(f"Загружен TXT: {filename}")
                except Exception as e:
                    logger.error(f"Ошибка при чтении TXT {filename}: {e}")
                    continue
            else:
                continue
            
            # Разбивка текста на chunks по 500 символов
            chunks = self._split_text(text_content, chunk_size=500)
            
            # Добавление chunks в списки для загрузки
            for i, chunk in enumerate(chunks):
                if chunk.strip():  # Пропускаем пустые chunks
                    doc_id = f"{filename}_chunk_{i}"
                    documents.append(chunk)
                    metadatas.append({
                        "source": filename,
                        "chunk_index": i,
                        "file_path": file_path
                    })
                    ids.append(doc_id)
                    doc_counter += 1
        
        # Загрузка документов в ChromaDB
        if documents:
            try:
                # Создание embeddings
                embeddings = self.embedding_model.encode(documents).tolist()
                
                # Добавление в коллекцию
                self.collection.add(
                    documents=documents,
                    embeddings=embeddings,
                    metadatas=metadatas,
                    ids=ids
                )
                logger.info(f"Успешно загружено {doc_counter} фрагментов из {len(set(m['source'] for m in metadatas))} файлов")
            except Exception as e:
                logger.error(f"Ошибка при загрузке документов в ChromaDB: {e}")
        else:
            logger.warning(f"Не найдено документов для загрузки в папке: {folder_path}")
    
    async def search(self, query: str, top_k: int = 3) -> list[str]:
        """
        Выполняет поиск релевантных фрагментов по запросу.
        
        Args:
            query: Поисковый запрос
            top_k: Количество возвращаемых результатов
            
        Returns:
            Список релевантных фрагментов текста
        """
        # Проверка на пустую базу
        if self.collection.count() == 0:
            logger.warning("База знаний пуста. Сначала загрузите документы.")
            return []
        
        try:
            # Создание embedding для запроса
            query_embedding = self.embedding_model.encode([query]).tolist()
            
            # Поиск в ChromaDB
            results = self.collection.query(
                query_embeddings=query_embedding,
                n_results=min(top_k, self.collection.count())
            )
            
            # Извлечение текстов из результатов
            if results and results['documents'] and len(results['documents']) > 0:
                documents = results['documents'][0]
                logger.info(f"Найдено {len(documents)} релевантных фрагментов для запроса: '{query[:50]}...'")
                return documents
            else:
                logger.info(f"Не найдено релевантных фрагментов для запроса: '{query[:50]}...'")
                return []
                
        except Exception as e:
            logger.error(f"Ошибка при поиске: {e}")
            return []
    
    def _split_text(self, text: str, chunk_size: int = 500) -> list[str]:
        """
        Разбивает текст на chunks заданного размера.
        
        Args:
            text: Исходный текст
            chunk_size: Размер chunk в символах
            
        Returns:
            Список chunks
        """
        chunks = []
        for i in range(0, len(text), chunk_size):
            chunk = text[i:i + chunk_size]
            chunks.append(chunk)
        return chunks
