yolov8n_seg 从ultralytics下载也可以安装ultralytics后命令行下载 https://docs.ultralytics.com/zh/models/yolov8/

python环境为310

pytorch版本为2.1.2

GPU==false

相机海康cs系列，镜头35mm

机器人法奥

实现效果：TCP与相机和机械臂进行通信，机械臂作为客户端，python作为服务端，当机械臂移动到拍照点时触发python服务，此服务内涵拍照-分割-计算抓取点位的流程，最终将抓取点位以机械臂可以理解的形式发送给客户端（通过九点标定的单应矩阵转换，Z值固定）
