import os
import uuid
import time
import math
import cv2
import gc
import numpy as np
import mediapipe as mp

from flask import Flask, request, jsonify, send_from_directory, render_template
from werkzeug.utils import secure_filename
from moviepy.editor import VideoFileClip

app = Flask(__name__)

# Configurations
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'outputs'
ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'mov', 'avi'}
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def allowed_file(filename, allowed_set):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_set

def rotate_image(image, angle):
    image_center = tuple(np.array(image.shape[1::-1]) / 2)
    rot_mat = cv2.getRotationMatrix2D(image_center, angle, 1.0)
    abs_cos = abs(rot_mat[0, 0])
    abs_sin = abs(rot_mat[0, 1])
    bound_w = int(image.shape[0] * abs_sin + image.shape[1] * abs_cos)
    bound_h = int(image.shape[0] * abs_cos + image.shape[1] * abs_sin)
    rot_mat[0, 2] += bound_w / 2 - image_center[0]
    rot_mat[1, 2] += bound_h / 2 - image_center[1]
    result = cv2.warpAffine(image, rot_mat, (bound_w, bound_h), flags=cv2.INTER_LINEAR, 
                            borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    return result

def overlay_image_alpha(img, img_overlay, x, y, alpha_mask):
    y1, y2 = max(0, y), min(img.shape[0], y + img_overlay.shape[0])
    x1, x2 = max(0, x), min(img.shape[1], x + img_overlay.shape[1])
    y1o, y2o = max(0, -y), min(img_overlay.shape[0], img.shape[0] - y)
    x1o, x2o = max(0, -x), min(img_overlay.shape[1], img.shape[1] - x)
    if y1 >= y2 or x1 >= x2 or y1o >= y2o or x1o >= x2o: return
    img_crop = img[y1:y2, x1:x2]
    img_overlay_crop = img_overlay[y1o:y2o, x1o:x2o]
    alpha = alpha_mask[y1o:y2o, x1o:x2o, np.newaxis] / 255.0
    img_crop[:] = alpha * img_overlay_crop[:, :, :3] + (1 - alpha) * img_crop

def process_video_motion(video_path, image_path, output_path, watermark):
    # MediaPipe Face Mesh yahan safely load hoga
    mp_face_mesh = mp.solutions.face_mesh
    
    img_overlay = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
    if img_overlay is None: raise Exception("Invalid image file.")
    if len(img_overlay.shape) == 3 and img_overlay.shape[2] == 3:
        img_overlay = cv2.cvtColor(img_overlay, cv2.COLOR_BGR2BGRA)

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    temp_video_path = output_path.replace(".mp4", "_temp.mp4")
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(temp_video_path, fourcc, fps, (w, h))

    with mp_face_mesh.FaceMesh(
        max_num_faces=5, 
        min_detection_confidence=0.5, 
        min_tracking_confidence=0.5
    ) as face_mesh:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret: break

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = face_mesh.process(rgb_frame)

            if results.multi_face_landmarks:
                for face_landmarks in results.multi_face_landmarks:
                    x_min, y_min = w, h
                    x_max, y_max = 0, 0
                    
                    for lm in face_landmarks.landmark:
                        x, y = int(lm.x * w), int(lm.y * h)
                        if x < x_min: x_min = x
                        if y < y_min: y_min = y
                        if x > x_max: x_max = x
                        if y > y_max: y_max = y

                    left_eye = face_landmarks.landmark[33]
                    right_eye = face_landmarks.landmark[263]
                    dx = (right_eye.x - left_eye.x) * w
                    dy = (right_eye.y - left_eye.y) * h
                    angle = math.degrees(math.atan2(dy, dx))

                    face_w, face_h = x_max - x_min, y_max - y_min
                    if face_w <= 0 or face_h <= 0: continue
                    
                    scale_factor = 1.6 
                    new_w = max(10, int(face_w * scale_factor))
                    new_h = max(10, int(face_h * scale_factor))

                    resized_overlay = cv2.resize(img_overlay, (new_w, new_h))
                    rotated_overlay = rotate_image(resized_overlay, -angle)
                    alpha_mask = rotated_overlay[:, :, 3]

                    center_x = x_min + face_w // 2
                    center_y = y_min + face_h // 2
                    start_x = center_x - rotated_overlay.shape[1] // 2
                    start_y = center_y - rotated_overlay.shape[0] // 2

                    overlay_image_alpha(frame, rotated_overlay, start_x, start_y, alpha_mask)

            if watermark:
                cv2.putText(frame, watermark, (30, h - 30), cv2.FONT_HERSHEY_DUPLEX, 1, (255, 255, 255), 2, cv2.LINE_AA)
                cv2.putText(frame, watermark, (30, h - 30), cv2.FONT_HERSHEY_DUPLEX, 1, (0, 243, 255), 1, cv2.LINE_AA)

            out.write(frame)

    cap.release()
    out.release()

    # Audio Merge
    orig_clip = VideoFileClip(video_path)
    final_clip = VideoFileClip(temp_video_path)
    if orig_clip.audio:
        final_clip = final_clip.set_audio(orig_clip.audio)
    
    final_clip.write_videofile(output_path, codec="libx264", audio_codec="aac", logger=None)
    
    orig_clip.close()
    final_clip.close()
    if os.path.exists(temp_video_path): os.remove(temp_video_path)
    
    gc.collect()

def cleanup_old_files():
    now = time.time()
    for folder in[UPLOAD_FOLDER, OUTPUT_FOLDER]:
        for f in os.listdir(folder):
            path = os.path.join(folder, f)
            if os.path.isfile(path) and os.stat(path).st_mtime < now - 1800:
                os.remove(path)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/process', methods=['POST'])
def process_api():
    cleanup_old_files()

    if 'video' not in request.files or 'image' not in request.files:
        return jsonify({"error": "Video and Image files are required."}), 400

    video = request.files['video']
    image = request.files['image']
    watermark = request.form.get('watermark', '').strip()

    uid = str(uuid.uuid4())
    video_ext = video.filename.rsplit('.', 1)[1].lower()
    img_ext = image.filename.rsplit('.', 1)[1].lower()

    video_path = os.path.join(UPLOAD_FOLDER, f"{uid}_vid.{video_ext}")
    image_path = os.path.join(UPLOAD_FOLDER, f"{uid}_img.{img_ext}")
    output_filename = f"{uid}_output.mp4"
    output_path = os.path.join(OUTPUT_FOLDER, output_filename)

    video.save(video_path)
    image.save(image_path)

    try:
        process_video_motion(video_path, image_path, output_path, watermark)
        if os.path.exists(video_path): os.remove(video_path)
        if os.path.exists(image_path): os.remove(image_path)

        return jsonify({
            "success": True,
            "download_url": f"/download/{output_filename}"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/download/<filename>')
def download(filename):
    return send_from_directory(OUTPUT_FOLDER, filename, as_attachment=True)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, threaded=True)
