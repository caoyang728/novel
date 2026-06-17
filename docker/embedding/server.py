"""
Embedding 服务 - 加载本地模型并通过 HTTP 提供 embedding 接口
"""
import os
from fastapi import FastAPI
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

app = FastAPI(title="Novel Agent Embedding Service")

model_name = os.getenv("MODEL_NAME", "BAAI/bge-large-zh-v1.5")
device = os.getenv("DEVICE", "cpu")

model = SentenceTransformer(model_name, device=device)


class EmbeddingRequest(BaseModel):
    texts: list[str]


class EmbeddingResponse(BaseModel):
    embeddings: list[list[float]]
    dim: int


@app.post("/embed", response_model=EmbeddingResponse)
def embed(request: EmbeddingRequest):
    embeddings = model.encode(
        request.texts,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return EmbeddingResponse(
        embeddings=embeddings.tolist(),
        dim=embeddings.shape[1],
    )


@app.get("/health")
def health():
    return {"status": "ok", "model": model_name, "device": device}
