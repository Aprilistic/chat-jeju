import asyncio
from typing import List, Optional

from chromadb import Collection, QueryResult
from fastapi import UploadFile

from app.clients import OpenAIClient, UpstageClient
from app.core.db import get_chrome_client
from app.core.logger import logger
from app.models.schemas import EmbeddingResult, LayoutAnalysisResult, EmbeddingContext, EmbeddingContextList


class EmbeddingService:

    def __init__(self, open_ai_client: OpenAIClient, upstage_client: UpstageClient):
        self.open_ai_client = open_ai_client
        self.upstage_client = upstage_client

    async def _embeddings(self, messages: List[str], model: str='solar-embedding-1-large-query') -> List[EmbeddingResult]:
        """
        Request embeddings from OpenAI API
        If you want to add extra logic, you can add it here. e.g. filtering, validation, rag, etc.

        Args:
            text (str): Text
            model (str, optional): Model name. Use query model for user query and passage model for passage.

        Returns:
            List[float]: Embedding response
        """
        result = await self.open_ai_client.embeddings(messages=messages, model=model)

        return result

    async def passage_embeddings(self, messages: List[str],
                                 model: str='solar-embedding-1-large-passage', 
                                 collection: str="embeddings", 
                                 id: str="data") -> List[EmbeddingResult]:
        """
        Request embeddings from OpenAI API for passage

        Args:
            messages (List[str]): Passage messages

        Returns:
            List[float]: Embedding response
        """

        results: List[EmbeddingResult] = await self.open_ai_client.embeddings(messages=messages, model=model)
        embeddings = [result.embedding for result in results]
        ids = [f"{id}_{i}" for i in range(len(messages))]
        
        async with get_chrome_client() as client:
            collection_name = f"embeddings-{collection}" if collection else "embeddings"
            logger.info(f'collection_name: {collection_name}')
            collection: Collection = await client.get_or_create_collection(collection_name)
            logger.info(f'collection: {collection}')
            await collection.add(
                documents=messages,
                embeddings=embeddings,
                ids=ids
            )
            
        return results

    async def pdf_embeddings(self, file: UploadFile, collection: str) -> List[EmbeddingResult]:
        """
        Request embeddings from OpenAI API for PDF file

        Args:
            file (UploadFile): PDF file

        Returns:
            List[float]: Embedding response
        """

        la_result: LayoutAnalysisResult = await self.upstage_client.layout_analysis(file=file.file)

        messages = []
        ids = []
        for element in la_result.elements:
            if element.text and len(element.text) > 10:
                messages.append(element.text)
                ids.append(f"{file.filename}_{element.id}_{element.page}")

        # Get embeddings for each text element by maxiumum 100 elenments
        embedding: List[List[EmbeddingResult]] = await asyncio.gather(
            *[self.open_ai_client.embeddings(messages=messages[i:i+100]) for i in range(0, len(messages), 100)]
        )

        results = []
        for emb in embedding:
            results.extend(emb)


        async with get_chrome_client() as client:
            collection_name = f"embeddings-{collection}" if collection else "embeddings"

            collection: Collection = await client.get_or_create_collection(collection_name)
            await collection.add(
                documents=messages,
                embeddings=[result.embedding for result in results],
                ids=ids
            )

        return results

    async def rag(self, messages: List[str], model: str='solar-embedding-1-large-query', embedding_collection="embeddings") -> Optional[EmbeddingContextList]:
        """
        Search embeddings from ChromaDB top-10 similar embeddings

        Args:
            query (str): User query messages.
            model (str, optional): Model name. Use query model for user query.

        Returns:
            List[float]: Embedding response
        """

        embeddings: List[EmbeddingResult] = await self.open_ai_client.embeddings(messages=messages, model=model)

        async with get_chrome_client() as client:
            collection: Collection = await client.get_collection(embedding_collection)
            result: QueryResult = await collection.query(
                query_embeddings=[embedding.embedding for embedding in embeddings],
                n_results=10)

        context = []
        for document in result.get('documents', []):
            context.extend([EmbeddingContext(text=doc) for doc in document])

        if context:
            result = EmbeddingContextList(context=context)

            return result
        else:
            return None
