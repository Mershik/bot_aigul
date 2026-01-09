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
        Инициализирует ChromaDB и создает коллекции для базы знаний.
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
        
        # Создание или получение коллекций
        try:
            # Коллекция для знаний бота-клиента
            self.client_collection = self.client.get_or_create_collection(
                name="client_knowledge",
                metadata={"description": "База знаний для бота-клиента"}
            )
            
            # Коллекция для эталонных скриптов (для судьи)
            self.scripts_collection = self.client.get_or_create_collection(
                name="sales_scripts",
                metadata={"description": "Эталонные скрипты для оценки"}
            )
            
            logger.info(f"Коллекции инициализированы. Клиент: {self.client_collection.count()}, Скрипты: {self.scripts_collection.count()}")
        except Exception as e:
            logger.error(f"Ошибка при инициализации коллекций: {e}")
            raise
    
    async def load_knowledge_base(self, base_path: str):
        """
        Загружает документы из указанной папки, распределяя их по коллекциям.
        
        Args:
            base_path: Путь к корневой папке базы знаний
        """
        if not os.path.exists(base_path):
            logger.error(f"Папка не найдена: {base_path}")
            return

        # Рекурсивный обход папок
        for root, dirs, files in os.walk(base_path):
            for filename in files:
                file_path = os.path.join(root, filename)
                
                # Определяем целевую коллекцию на основе пути
                if "scripts" in root.lower():
                    collection = self.scripts_collection
                    logger.info(f"Файл {filename} определен в коллекцию SCRIPTS")
                else:
                    collection = self.client_collection
                    logger.info(f"Файл {filename} определен в коллекцию CLIENT")

                await self._process_file(file_path, filename, collection)

    async def _process_file(self, file_path: str, filename: str, collection):
        """Вспомогательный метод для обработки и загрузки одного файла."""
        text_content = ""
        
        if filename.lower().endswith('.pdf'):
            try:
                with open(file_path, 'rb') as pdf_file:
                    pdf_reader = pypdf.PdfReader(pdf_file)
                    for page in pdf_reader.pages:
                        text_content += page.extract_text() + "\n"
            except Exception as e:
                logger.error(f"Ошибка при чтении PDF {filename}: {e}")
                return
        
        elif filename.lower().endswith('.txt'):
            try:
                with open(file_path, 'r', encoding='utf-8') as txt_file:
                    text_content = txt_file.read()
            except Exception as e:
                logger.error(f"Ошибка при чтении TXT {filename}: {e}")
                return
        else:
            return

        if not text_content.strip():
            return

        chunks = self._split_text(text_content, chunk_size=500)
        documents = []
        metadatas = []
        ids = []

        for i, chunk in enumerate(chunks):
            if chunk.strip():
                doc_id = f"{filename}_chunk_{i}_{collection.name}"
                documents.append(chunk)
                metadatas.append({
                    "source": filename,
                    "chunk_index": i,
                    "file_path": file_path
                })
                ids.append(doc_id)

        if documents:
            embeddings = self.embedding_model.encode(documents).tolist()
            collection.add(
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas,
                ids=ids
            )
            logger.info(f"Загружено {len(documents)} фрагментов из {filename} в {collection.name}")

    async def search(self, query: str, collection_type: str = "client", top_k: int = 3) -> list[str]:
        """
        Выполняет поиск в указанной коллекции.
        
        Args:
            query: Поисковый запрос
            collection_type: Тип коллекции ("client" или "scripts")
            top_k: Количество результатов
        """
        collection = self.scripts_collection if collection_type == "scripts" else self.client_collection
        
        if collection.count() == 0:
            logger.warning(f"Коллекция {collection.name} пуста.")
            return []
        
        try:
            query_embedding = self.embedding_model.encode([query]).tolist()
            results = collection.query(
                query_embeddings=query_embedding,
                n_results=min(top_k, collection.count())
            )
            
            if results and results['documents'] and len(results['documents']) > 0:
                return results['documents'][0]
            return []
        except Exception as e:
            logger.error(f"Ошибка при поиске в {collection.name}: {e}")
            return []
    
    def _split_text(self, text: str, chunk_size: int = 500) -> list[str]:
        chunks = []
        for i in range(0, len(text), chunk_size):
            chunks.append(text[i:i + chunk_size])
        return chunks
