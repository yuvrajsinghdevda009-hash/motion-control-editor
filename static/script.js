document.addEventListener('DOMContentLoaded', () => {
    const videoZone = document.getElementById('videoZone');
    const imageZone = document.getElementById('imageZone');
    const videoInput = document.getElementById('videoInput');
    const imageInput = document.getElementById('imageInput');
    
    // File Handlers
    const setupDropZone = (zone, input, labelId) => {
        zone.addEventListener('click', () => input.click());
        zone.addEventListener('dragover', (e) => { e.preventDefault(); zone.classList.add('dragover'); });
        zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
        zone.addEventListener('drop', (e) => {
            e.preventDefault();
            zone.classList.remove('dragover');
            if (e.dataTransfer.files.length) {
                input.files = e.dataTransfer.files;
                document.getElementById(labelId).innerText = input.files[0].name;
            }
        });
        input.addEventListener('change', () => {
            if (input.files.length) document.getElementById(labelId).innerText = input.files[0].name;
        });
    };

    setupDropZone(videoZone, videoInput, 'videoName');
    setupDropZone(imageZone, imageInput, 'imageName');

    // Form Submission
    document.getElementById('uploadForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        
        if (!videoInput.files[0] || !imageInput.files[0]) {
            showError("Please upload both a video and an image.");
            return;
        }

        const formData = new FormData();
        formData.append('video', videoInput.files[0]);
        formData.append('image', imageInput.files[0]);
        formData.append('watermark', document.getElementById('watermark').value);

        // UI State Change
        document.getElementById('uploadForm').classList.add('hidden');
        document.getElementById('loadingUI').classList.remove('hidden');
        document.getElementById('errorToast').classList.add('hidden');

        try {
            const response = await fetch('/api/process', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (response.ok) {
                document.getElementById('loadingUI').classList.add('hidden');
                document.getElementById('resultUI').classList.remove('hidden');
                
                const videoEl = document.getElementById('resultVideo');
                videoEl.src = result.download_url;
                
                document.getElementById('downloadBtn').href = result.download_url;
            } else {
                throw new Error(result.error || "Processing failed.");
            }
        } catch (error) {
            document.getElementById('loadingUI').classList.add('hidden');
            document.getElementById('uploadForm').classList.remove('hidden');
            showError(error.message);
        }
    });

    function showError(msg) {
        const toast = document.getElementById('errorToast');
        toast.innerText = msg;
        toast.classList.remove('hidden');
        setTimeout(() => toast.classList.add('hidden'), 5000);
    }
});
