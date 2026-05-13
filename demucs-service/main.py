
import os
import shutil
import subprocess
import uuid
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse

app = FastAPI()

@app.get("/")
def read_root():
    return {"status": "online"}

@app.post("/separate")
async def separate_audio(file: UploadFile = File(...)):
    # Create a unique temporary directory for this request
    temp_dir = f"/tmp/{uuid.uuid4()}"
    os.makedirs(temp_dir)
    input_path = os.path.join(temp_dir, file.filename)

    try:
        # Save the uploaded file
        with open(input_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Determine the device to use (cpu or cuda)
        device = os.getenv("DEMUCS_DEVICE", "cpu")
        device_arg = f"-d {device}"

        # Run demucs command safely
        output_base_dir = os.path.join(temp_dir, "separated")
        cmd = [
            'python3', '-m', 'demucs',
            '-d', device,
            '--out', output_base_dir,
            input_path
        ]
        subprocess.run(cmd, check=True)

        # Dynamically find the output directory created by demucs
        # It should be the only subdirectory inside `output_base_dir`
        try:
            model_name = next(d for d in os.listdir(output_base_dir) if os.path.isdir(os.path.join(output_base_dir, d)))
            separated_files_dir = os.path.join(output_base_dir, model_name, os.path.splitext(file.filename)[0])
            if not os.path.isdir(separated_files_dir):
                raise StopIteration # Trigger fallback
        except StopIteration:
            # Fallback search if the directory structure is not as expected
            found = False
            for root, dirs, files in os.walk(output_base_dir):
                if any(f.endswith(('.wav', '.mp3')) for f in files):
                    separated_files_dir = root
                    found = True
                    break
            if not found:
                raise Exception("Could not find the output directory from demucs.")


        # Create a zip file of the separated tracks
        zip_path = os.path.join(temp_dir, "separated_tracks")
        shutil.make_archive(zip_path, 'zip', separated_files_dir)
        zip_path_with_ext = f"{zip_path}.zip"

        return FileResponse(zip_path_with_ext, media_type='application/zip', filename=f"{os.path.splitext(file.filename)[0]}_separated.zip")

    finally:
        # Clean up the temporary directory
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
