import argparse
import sys

import cv2


def main() -> int:
    parser = argparse.ArgumentParser(description="SIFT + FLANN real-time matcher")
    parser.add_argument("--ref", default="gambar.jpeg", help="Path gambar referensi")
    parser.add_argument("--camera", type=int, default=0, help="Index kamera")
    parser.add_argument("--ratio", type=float, default=0.7, help="Lowe ratio threshold")
    args = parser.parse_args()

    detector = cv2.SIFT_create()

    # FLANN untuk descriptor float (SIFT) menggunakan KDTree.
    index_params = dict(algorithm=1, trees=5)
    search_params = dict(checks=50)
    flann = cv2.FlannBasedMatcher(index_params, search_params)

    img_ref = cv2.imread(args.ref)
    if img_ref is None:
        print(f"Error: file referensi '{args.ref}' tidak ditemukan.")
        return 1

    gray_ref = cv2.cvtColor(img_ref, cv2.COLOR_BGR2GRAY)
    kp_ref, desc_ref = detector.detectAndCompute(gray_ref, None)
    if desc_ref is None or len(kp_ref) == 0:
        print("Error: tidak ada keypoint/descriptor pada gambar referensi.")
        return 1

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        print(f"Error: kamera index {args.camera} tidak dapat dibuka.")
        return 1

    print("Tekan 'q' untuk keluar.")
    while True:
        ok, frame = cap.read()
        if not ok:
            break

        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        kp_frame, desc_frame = detector.detectAndCompute(gray_frame, None)

        result_img = frame
        if desc_frame is not None and len(kp_frame) > 0:
            matches = flann.knnMatch(desc_ref, desc_frame, k=2)
            good_matches = []
            for pair in matches:
                if len(pair) == 2:
                    m, n = pair
                    if m.distance < args.ratio * n.distance:
                        good_matches.append(m)

            result_img = cv2.drawMatches(
                img_ref,
                kp_ref,
                frame,
                kp_frame,
                good_matches,
                None,
                flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS,
            )
            cv2.putText(
                result_img,
                f"Good Matches: {len(good_matches)}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 0),
                2,
            )

        cv2.imshow("FLANN Matching - SIFT", result_img)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    sys.exit(main())
