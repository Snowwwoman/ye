import socket
import os
import time
import subprocess
import sys
import threading

# Use script directory + `end` folder
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
END_DIR = os.path.join(BASE_DIR, "end")

HOST = "0.0.0.0"
PORT = 5020
# camera script path (two levels up from project2 -> camera/1.py)
CAMERA_SCRIPT = os.path.abspath(os.path.join(BASE_DIR, '..', '..', 'camera', '1.py'))

# Prevent concurrent camera/main pipeline runs which may conflict on files/hardware
CAMERA_LOCK = threading.Lock()


def read_pose(path):
    with open(path, "r") as f:
        line = f.readline().strip()
    parts = line.split()
    if len(parts) < 3:
        raise ValueError("pose file must contain at least X Y RZ")
    x, y, rz = map(float, parts[:3])
    return f"{x:.3f} {y:.3f} {rz:.3f}\n"


def find_first_pose(end_dir):
    # return the newest (most recently modified) .txt file in end_dir
    if not os.path.isdir(end_dir):
        return None
    files = [os.path.join(end_dir, n) for n in os.listdir(end_dir) if n.lower().endswith('.txt')]
    files = [f for f in files if os.path.isfile(f)]
    if files:
        # choose by modification time (most recent)
        return max(files, key=lambda p: os.path.getmtime(p))

    # fallback: if no files at end/, also check end/sent/ and return newest there
    sent_dir = os.path.join(end_dir, 'sent')
    if os.path.isdir(sent_dir):
        sfiles = [os.path.join(sent_dir, n) for n in os.listdir(sent_dir) if n.lower().endswith('.txt')]
        sfiles = [f for f in sfiles if os.path.isfile(f)]
        if sfiles:
            return max(sfiles, key=lambda p: os.path.getmtime(p))

    return None


def main():
    def handle_client(conn, addr):
        with conn:
            print("Connected by", addr)
            # loop to allow multiple requests over same connection
            while True:
                try:
                    data = conn.recv(1024)
                except Exception:
                    break
                if not data:
                    break

                print("Request:", data.decode())

                # Run camera capture script first
                def run_camera_script(path, timeout=20):
                    if not os.path.isfile(path):
                        return False, f"Camera script not found: {path}"
                    try:
                        proc = subprocess.run([sys.executable, path], capture_output=True, text=True, errors='replace', timeout=timeout)
                        out = (proc.stdout or "") + (proc.stderr or "")
                        if proc.returncode != 0:
                            return False, f"Camera script failed (code {proc.returncode}): {out}"
                        return True, out
                    except Exception as e:
                        return False, str(e)

                # serialize camera and main pipeline to avoid hardware/file conflicts
                # If pipeline is busy, reply BUSY immediately to avoid queuing
                acquired = CAMERA_LOCK.acquire(blocking=False)
                if not acquired:
                    try:
                        conn.sendall(b'BUSY\n')
                    except Exception:
                        pass
                    print('Pipeline busy — replied BUSY')
                    continue
                try:
                    print('Starting camera capture:', CAMERA_SCRIPT)
                    ok, cam_out = run_camera_script(CAMERA_SCRIPT)
                    try:
                        log_dir = os.path.join(END_DIR, 'sent')
                        os.makedirs(log_dir, exist_ok=True)
                        cam_log = os.path.join(log_dir, 'camera_run.log')
                        with open(cam_log, 'a', encoding='utf-8') as cf:
                            cf.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}\t{CAMERA_SCRIPT}\treturn:{ok}\t{cam_out.strip()}\n")
                    except Exception:
                        pass

                    if not ok:
                        err_msg = f"ERR CAM {cam_out}\n"
                        try:
                            conn.sendall(err_msg.encode())
                        except Exception:
                            pass
                        print('Camera run failed:', cam_out)
                        continue

                    # After successful camera capture, also run the full processing pipeline
                    # (main.py) to create/update files under `end/` so the server can find poses.
                    print('Starting main pipeline: main.py')
                    try:
                        main_path = os.path.join(BASE_DIR, 'main.py')
                        if os.path.isfile(main_path):
                            proc = subprocess.run([sys.executable, main_path], capture_output=True, text=True, errors='replace', timeout=120)
                            main_out = (proc.stdout or '') + (proc.stderr or '')
                            try:
                                log_dir = os.path.join(END_DIR, 'sent')
                                os.makedirs(log_dir, exist_ok=True)
                                with open(os.path.join(log_dir, 'main_run.log'), 'a', encoding='utf-8') as mf:
                                    mf.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}\t{main_path}\treturn:{proc.returncode}\t{main_out.strip()}\n")
                            except Exception:
                                pass
                            if proc.returncode != 0:
                                print('main.py returned non-zero:', proc.returncode)
                        else:
                            print('main.py not found, skipping full pipeline run')
                    except Exception as e:
                        print('Error running main.py:', e)

                    pose_path = find_first_pose(END_DIR)
                finally:
                    CAMERA_LOCK.release()
                # end CAMERA_LOCK

                used_source = None
                if not pose_path:
                    next_txt = os.path.join(BASE_DIR, 'next.txt')
                    if os.path.exists(next_txt):
                        pose_path = next_txt
                        used_source = 'next.txt'

                if not pose_path:
                    try:
                        conn.sendall(b"NO_POSE\n")
                    except Exception:
                        pass
                    print('No pose available')
                    continue

                try:
                    reply = read_pose(pose_path)
                except Exception as e:
                    try:
                        conn.sendall(f"ERR {e}\n".encode())
                    except Exception:
                        pass
                    print('Error reading pose:', e)
                    continue

                try:
                    conn.sendall(reply.encode())
                except Exception:
                    print('Failed to send reply')
                    break

                src = used_source if used_source else 'end'
                print(f"Send (from {src}):", reply.strip())

                # log sent info (timestamp, filename, reply) — do NOT move files
                try:
                    log_dir = os.path.join(END_DIR, 'sent')
                    os.makedirs(log_dir, exist_ok=True)
                    log_path = os.path.join(log_dir, 'sent.log')
                    with open(log_path, 'a', encoding='utf-8') as lf:
                        lf.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}\t{os.path.basename(pose_path)}\t{reply.strip()}\n")
                    print('Logged sent to', log_path)
                except Exception as e:
                    print('Logging failed:', e)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen(5)

        print(f"Vision server listening on {HOST}:{PORT}")

        while True:
            conn, addr = s.accept()
            # handle each client in a separate thread; handler will loop per-connection
            t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            t.start()


if __name__ == "__main__":
    main()