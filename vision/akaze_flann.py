import cv2
import numpy as np

# 1. Inisialisasi AKAZE
akaze = cv2.AKAZE_create()

# 2. Inisialisasi FLANN Matcher untuk Binary Descriptor (LSH)
FLANN_INDEX_LSH = 6
index_params = dict(algorithm = FLANN_INDEX_LSH,
                    table_number = 6,      # 12
                    key_size = 12,          # 20
                    multi_probe_level = 1) # 2
search_params = dict(checks=50) # jumlah iterasi pencarian

flann = cv2.FlannBasedMatcher(index_params, search_params)

# 3. Siapkan Gambar Referensi
img_ref = cv2.imread('gambar.jpeg')
if img_ref is None:
    print("Error: gambar.jpeg tidak ditemukan!")
    exit()

gray_ref = cv2.cvtColor(img_ref, cv2.COLOR_BGR2GRAY)
kp_ref, desc_ref = akaze.detectAndCompute(gray_ref, None)

# 4. Buka Webcam
cap = cv2.VideoCapture(0)

while True:
    ret, frame = cap.read()
    if not ret: break

    gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    kp_frame, desc_frame = akaze.detectAndCompute(gray_frame, None)

    # Pastikan deskriptor ditemukan di kedua gambar
    if desc_ref is not None and desc_frame is not None:
        # Menggunakan k-Nearest Neighbors (k=2) untuk Lowe's Ratio Test
        matches = flann.knnMatch(desc_ref, desc_frame, k=2)

        # Filter matches menggunakan Lowe's Ratio Test (Mencari match yang benar-benar unik)
        good_matches = []
        for m_n in matches:
            if len(m_n) == 2:
                m, n = m_n
                if m.distance < 0.7 * n.distance:
                    good_matches.append(m)

        # Gambar hasil
        result_img = cv2.drawMatches(img_ref, kp_ref, frame, kp_frame, good_matches, None, 
                                     flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS)
        
        cv2.putText(result_img, f"Good Matches: {len(good_matches)}", (10, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    else:
        result_img = frame

    cv2.imshow('FLANN Matching - AKAZE', result_img)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
