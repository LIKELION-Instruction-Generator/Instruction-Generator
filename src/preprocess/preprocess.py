from loguru import logger
from utils import load_config
from dotenv import load_dotenv
import re
import os
import anthropic

config = load_config("../utils/config.yaml")
data_path = config["data"]["script_path"]
processed_script_path = config["data"]["output_path"]
env_path = config["env"]["env_path"]

load_dotenv(env_path)
api_key = os.getenv("ANTHROPIC_API_KEY")

def load_txt_file(file_path):
    try:
        with open(file_path, "r", encoding = "utf-8") as f:
            content = f.read()
            return content
    except FileNotFoundError as e:
        logger.info(f"지정된 경로에서 파일을 찾을 수 없습니다: {file_path}")
        raise FileNotFoundError(f"파일 로드 실패: {file_path}") from e

def preprocess_script(raw_text):
    pattern = r"<\d{2}:\d{2}:\d{2}>\s[a-z0-9]+:\s"
    clean_text = re.sub(pattern, "", raw_text)
    clean_text = clean_text.replace("\n", " ").strip()
    clean_text = re.sub(r"\s+", " ", clean_text)
    
    # 문장 단위 분리
    sentences = re.split(r'(?<=[.!?])\s+', clean_text)
    return sentences

def chunk_text(sentences, max_chars=2000):
    chunks = []
    current_chunk = ""
    for sentence in sentences:
        if len(current_chunk) + len(sentence) + 1 > max_chars and current_chunk:
            chunks.append(current_chunk.strip())
            current_chunk = sentence
        else:
            current_chunk += " " + sentence if current_chunk else sentence
    if current_chunk:
        chunks.append(current_chunk.strip())
    return chunks

def preprocess_with_llm(chunks, output_path = processed_script_path):
    client = anthropic.Anthropic()
    results = []

    for i, chunk in enumerate(chunks):
        logger.info(f"청크 {i+1}/{len(chunks)} 처리 중...")
        message = client.messages.create(
            model = "claude-opus-4-6",
            max_tokens = 4000,
            messages = [
                {
                    "role": "user",
                    "content": 
                        f"""
                        아래에 주어지는 문장을 올바르게 복원해주세요. 
                        불필요한 문장이나 단어를 포함하지말고, 복원한 문장만 출력해주세요.
                        문장이 너무 길어지면 개행을 통해 다음 줄에 작성하세요.
                        {chunk}
                        """
                }
            ]
        )
        results.append(message.content[0].text)
    
    full_script = "".join(results)

    os.makedirs(os.path.dirname(output_path), exist_ok = True)
    with open(output_path, "w", encoding = "utf-8") as f:
        f.write(full_script)
    logger.info(f"저장 완료: {output_path}")
    
    return full_script

if __name__ == "__main__":
    texts = load_txt_file(data_path)
    processed_text_list = preprocess_script(texts)
    chunks = chunk_text(processed_text_list, max_chars = 2000)
    result = preprocess_with_llm(chunks)