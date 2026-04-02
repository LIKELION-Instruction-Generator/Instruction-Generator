import chromadb
from sentence_transformers import SentenceTransformer
from utils import load_config
import uuid

config = load_config("../utils/config.yaml")
text_file_path = config["data"]["processed_script_path"]

def ingest_scripts_manually(file_path, db_path = "../data/vector_db"):
    model = SentenceTransformer('BAAI/bge-m3')

    with open(file_path, 'r', encoding='utf-8') as f:
        text = f.read()
    
    chunk_size = 500
    overlap = 100
    chunks = []
    for i in range(0, len(text), chunk_size - overlap):
        chunks.append(text[i:i + chunk_size])
    client = chromadb.PersistentClient(path=db_path)
    
    collection = client.get_or_create_collection(name="lecture_scripts")

    for i, chunk in enumerate(chunks):
        embedding = model.encode(chunk).tolist()
        
        collection.add(
            ids=[str(uuid.uuid4())], # 유니크한 ID 생성
            embeddings=[embedding],
            documents=[chunk],
            metadatas=[{"source": file_path, "index": i}]
        )

    print(f"총 {len(chunks)}개의 조각이 저장되었습니다.")
    return collection

# 사용 예시
collection = ingest_scripts_manually(text_file_path)