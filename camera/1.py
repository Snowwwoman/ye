import os
import sys
import time
import ctypes
import numpy as np
import cv2

# ---------------- SDK 路径 ----------------
RUNTIME_DLL_DIR = r"C:\Program Files (x86)\Common Files\MVS\Runtime\Win64_x64"
if os.path.isdir(RUNTIME_DLL_DIR):
    os.environ['PATH'] = RUNTIME_DLL_DIR + ';' + os.environ.get('PATH', '')

SDK_PATH = r"C:\Program Files (x86)\Common Files\MVS\Development\Samples\Python"
mvimport_dir = os.path.join(SDK_PATH, 'MvImport')
if SDK_PATH not in sys.path:
    sys.path.insert(0, SDK_PATH)
# 将 MvImport 文件夹也加入 sys.path，样例模块使用顶级导入
if os.path.isdir(mvimport_dir) and mvimport_dir not in sys.path:
    sys.path.insert(0, mvimport_dir)

# 尝试多种导入方式以兼容不同示例布局
# 有些 SDK 示例模块内部遗漏了 `import os`，在导入前把 os 注入到 builtins，
# 以使模块内部对 os.path 的调用能正常工作而不用修改 SDK 文件。
import builtins
builtins.os = __import__('os')
try:
    from MvImport.MvCameraControl_class import *
    from MvImport.MvErrorDefine_const import *
    from MvImport.PixelType_header import *
except Exception:
    try:
        from MvCameraControl_class import *
    except Exception as e:
        print('导入 SDK 模块失败:', e)
        print('确保 SDK_PATH 或 MvImport 路径正确。已尝试路径：', SDK_PATH, mvimport_dir)
        sys.exit(1)

# ---------------- 配置 ----------------
TARGET_IP = "192.168.6.33"   # 指定相机 IP
SAVE_DIR = r"C:\Users\Administrator\Desktop\ye\vision\project2\data\images"   # 保存目录
os.makedirs(SAVE_DIR, exist_ok=True)
image_index = 0

# ---------------- 回调函数 ----------------
def image_callback(pData, pFrameInfo, pUser):
    global image_index
    frame_info = ctypes.cast(
        pFrameInfo, ctypes.POINTER(MV_FRAME_OUT_INFO_EX)
    ).contents

    width = frame_info.nWidth
    height = frame_info.nHeight

    # 转 numpy
    img = np.frombuffer(
        ctypes.string_at(pData, width * height * 3),
        dtype=np.uint8
    ).reshape((height, width, 3))

    # RGB -> BGR (OpenCV)
    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

    # 保存文件
    filename = os.path.join(SAVE_DIR, f"img_{image_index:06d}.png")
    cv2.imwrite(filename, img)
    image_index += 1
    print(f"Saved: {filename}")

# ---------------- 主函数 ----------------
def main():
    global image_index

    # 枚举设备
    cam = MvCamera()
    device_list = MV_CC_DEVICE_INFO_LIST()
    ret = cam.MV_CC_EnumDevices(MV_GIGE_DEVICE, device_list)
    if ret != 0 or device_list.nDeviceNum == 0:
        print("No GigE camera found")
        return

    # 查找指定 IP 的相机
    dev_info = None
    for i in range(device_list.nDeviceNum):
        tmp_info = ctypes.cast(
            device_list.pDeviceInfo[i],
            ctypes.POINTER(MV_CC_DEVICE_INFO)
        ).contents
        # Diagnostic prints to inspect types when casting
        if True:
            try:
                print('DEBUG: SpecialInfo type:', type(tmp_info.SpecialInfo))
                print('DEBUG: stGigEInfo repr:', repr(getattr(tmp_info.SpecialInfo, 'stGigEInfo', None)))
            except Exception as _:
                pass
        # stGigEInfo is already a structure instance in this wrapper, use directly
        gige_info = tmp_info.SpecialInfo.stGigEInfo
        ip_str = "{}.{}.{}.{}".format(
            (gige_info.nCurrentIp >> 24) & 0xFF,
            (gige_info.nCurrentIp >> 16) & 0xFF,
            (gige_info.nCurrentIp >> 8) & 0xFF,
            gige_info.nCurrentIp & 0xFF
        )
        if ip_str == TARGET_IP:
            dev_info = tmp_info
            break

    if dev_info is None:
        print(f"Camera with IP {TARGET_IP} not found")
        return

    # 创建句柄
    cam = MvCamera()
    ret = cam.MV_CC_CreateHandle(dev_info)
    if ret != 0:
        print("Create handle failed")
        return

    # 打开设备
    ret = cam.MV_CC_OpenDevice(MV_ACCESS_Exclusive, 0)
    if ret != 0:
        print("Open device failed")
        return

    # 关闭触发模式（连续采集）
    cam.MV_CC_SetEnumValue("TriggerMode", MV_TRIGGER_MODE_OFF)

    # 单次抓拍：使用回调模式，但在接收到第一帧后停止
    done = {'flag': False}

    def single_image_callback(pData, pFrameInfo, pUser):
        # 与上面的 image_callback 类似，但在保存后标记完成并停止抓图
        try:
            frame_info = ctypes.cast(pFrameInfo, ctypes.POINTER(MV_FRAME_OUT_INFO_EX)).contents
            width = frame_info.nWidth
            height = frame_info.nHeight
            img = np.frombuffer(ctypes.string_at(pData, width * height * 3), dtype=np.uint8).reshape((height, width, 3))
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
            timestamp = time.strftime('%Y%m%d_%H%M%S')
            save_path = os.path.join(SAVE_DIR, f"single_{timestamp}.png")
            cv2.imwrite(save_path, img)
            print(f"Saved single image: {save_path}")
        except Exception as e:
            print(f"Callback process error: {e}")
        finally:
            done['flag'] = True
            try:
                cam.MV_CC_StopGrabbing()
            except Exception:
                pass

    # 创建 C 回调并注册
    CALLBACK_FUN = ctypes.CFUNCTYPE(None, ctypes.POINTER(ctypes.c_ubyte), ctypes.POINTER(MV_FRAME_OUT_INFO_EX), ctypes.c_void_p)
    cb = CALLBACK_FUN(single_image_callback)
    cam.MV_CC_RegisterImageCallBackForRGB(cb, None)
    cam._py_callback_ref = cb

    # 开始取流并等待回调完成
    cam.MV_CC_StartGrabbing()
    timeout = 10.0
    start_t = time.time()
    while not done['flag'] and (time.time() - start_t) < timeout:
        time.sleep(0.05)

    # 清理
    try:
        cam.MV_CC_StopGrabbing()
    except Exception:
        pass
    cam.MV_CC_CloseDevice()
    cam.MV_CC_DestroyHandle()
    if not done['flag']:
        print('Single capture timed out')
    else:
        print('Single capture finished')

if __name__ == "__main__":
    main()