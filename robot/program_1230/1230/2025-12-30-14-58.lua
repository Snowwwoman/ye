--------------------------------
-- 视觉服务配置
--------------------------------
VISION_IP   = "192.168.6.83"
VISION_PORT = 5020
SOCKET_NAME = "socket_0"

tcp = 0

--------------------------------
-- 固定笛卡尔姿态
--------------------------------
FIX_Z  = 88
FIX_RX = 179
FIX_RY = 0.5

--------------------------------
-- MoveL 参数
--------------------------------
TOOL_NUM      = 0
WORKPIECE_NUM = 0

SPEED = 90
ACC   = 80
OVL   = 90

BLEND_R = -1
SEARCH_FLAG = 0
OFFSET_FLAG = 0

OFFSET_X, OFFSET_Y, OFFSET_Z = 0.0, 0.0, 0.0
OFFSET_RX, OFFSET_RY, OFFSET_RZ = 0.0, 0.0, 0.0

EX1, EX2, EX3, EX4 = 0.0, 0.0, 0.0, 0.0

OACC = 100
VEL_ACC_PARAM_MODE = 0

--------------------------------
-- 启动位
--------------------------------
print("机器人客户端启动...")

PTP(y放置移出点1,20,-1,0)
PTP(y抓取过渡点1,20,-1,0)
PTP(y抓取过渡点3,20,-1,0)
PTP(点4,20,-1,0)

--------------------------------
-- 主循环
--------------------------------
while true do

    ::LOOP_BEGIN::

    --------------------------------
    -- 未连接 → 建立连接
    --------------------------------
    if tcp == 0 then
        print("尝试连接视觉服务端...")
        tcp = SocketOpen(VISION_IP, VISION_PORT, SOCKET_NAME)
        WaitMs(300)
        goto LOOP_BEGIN
    end

    --------------------------------
    -- 请求视觉位姿
    --------------------------------
    SocketSendString("Need Pose", SOCKET_NAME, 0)
    print("已发送 Need Pose")

    --------------------------------
    -- 接收（带超时）
    --------------------------------
    recv_str = SocketReadString(SOCKET_NAME, 2000)

    if recv_str == nil or recv_str == "" then
        print("视觉无响应，重连")
        SocketClose(SOCKET_NAME)
        tcp = 0
        WaitMs(500)
        goto LOOP_BEGIN
    end

    print("收到视觉数据: [" .. recv_str .. "]")

    --------------------------------
    -- 无目标
    --------------------------------
    if recv_str == "NO_POSE" then
        print("当前无可抓取目标")
        WaitMs(200)
        goto LOOP_BEGIN
    end

    --------------------------------
    -- 解析位姿
    --------------------------------
    x, y, rz = string.match(
        recv_str,
        "([%-%d%.]+)%s+([%-%d%.]+)%s+([%-%d%.]+)"
    )

    if not x then
        print("位姿解析失败")
        goto LOOP_BEGIN
    end

    x  = tonumber(x)
    y  = tonumber(y)
    rz = tonumber(rz)

    print(string.format(
        "解析位姿: X=%.2f Y=%.2f RZ=%.2f", x, y, rz
    ))

    --------------------------------
    -- 逆解
    --------------------------------
    j1,j2,j3,j4,j5,j6 = GetInverseKin(
        WORKPIECE_NUM,
        x, y, FIX_Z,
        FIX_RX, FIX_RY, rz,
        -1
    )

    --------------------------------
    -- 抓取 MoveL
    --------------------------------
    ret = MoveL(
        j1,j2,j3,j4,j5,j6,
        x, y, FIX_Z,
        FIX_RX, FIX_RY, rz,
        TOOL_NUM,
        WORKPIECE_NUM,
        SPEED,
        ACC,
        OVL,
        EX1, EX2, EX3, EX4,
        BLEND_R,
        SEARCH_FLAG,
        OFFSET_FLAG,
        OFFSET_X, OFFSET_Y, OFFSET_Z,
        OFFSET_RX, OFFSET_RY, OFFSET_RZ,
        OACC,
        VEL_ACC_PARAM_MODE
    )

    if ret ~= 0 then
        print("MoveL 执行失败，跳过本次")
        goto LOOP_BEGIN
    end

    --------------------------------
    -- 夹爪动作
    --------------------------------
    SetDO(0,1,0,1)
    WaitMs(1500)

    --------------------------------
    -- 放置流程
    --------------------------------
    PTP(y抓取移出点1,20,-1,0)
    PTP(y抓取过渡点5,20,-1,0)
    PTP(y抓取过渡点3,20,-1,0)
    PTP(y抓取过渡点1,20,-1,0)
    PTP(y放置点1,20,-1,0)

    SetDO(0,0,0,1)   -- 松爪
    WaitMs(1000)

    PTP(y放置移出点1,20,-1,0)

    --------------------------------
    -- 一轮完成
    --------------------------------
    print("本次抓取完成，进入下一轮")
    WaitMs(300)

end