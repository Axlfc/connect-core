import os
import shutil
import subprocess
import uuid
from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse

app = FastAPI()

def cleanup(path: str):
    if os.path.exists(path):
        shutil.rmtree(path)

@app.get("/")
def health():
    return {"status": "online", "device": "RTX 5070", "service": "demucs"}

@app.post("/separate")
async def separate_audio(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    job_id = str(uuid.uuid4())
    temp_dir = f"/tmp/{job_id}"
    os.makedirs(temp_dir, exist_ok=True)
    
    # Sanitizar el nombre del archivo
    safe_filename = "".join([c if c.isalnum() or c in "._-" else "_" for c in file.filename])
    input_path = os.path.join(temp_dir, safe_filename)

    try:
        with open(input_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        output_dir = os.path.join(temp_dir, "out")
        
        # Ejecución de Demucs usando el modelo HTDemucs
        cmd = [
            "python3", "-m", "demucs.separate",
            "-d", "cuda",
            "-n", "htdemucs",
            "--out", output_dir,
            input_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"Demucs Error: {result.stderr}")

        # Localizar las pistas separadas
        folder_name = os.path.splitext(safe_filename)[0]
        pistas_dir = os.path.join(output_dir, "htdemucs", folder_name)
        
        # Comprimir resultados
        zip_path = os.path.join(temp_dir, f"{folder_name}_separated")
        shutil.make_archive(zip_path, 'zip', pistas_dir)
        
        background_tasks.add_task(cleanup, temp_dir)
        return FileResponse(f"{zip_path}.zip", filename=f"{folder_name}_separated.zip")

    except Exception as e:
        cleanup(temp_dir)
        raise HTTPException(status_code=500, detail=str(e))