VISION_IP   = "192.168.6.83"
VISION_PORT = 5020
SOCKET_NAME = "socket_0"

tcp = 0

-- 固定笛卡尔姿态
FIX_Z  = 88
FIX_RX = 179
FIX_RY = 0.5

-- MoveL 参数
TOOL_NUM      = 0    
WORKPIECE_NUM = 0    

SPEED = 90       
ACC   = 80        
OVL   = 90        

BLEND_R = -1      
SEARCH_FLAG = 0   
OFFSET_FLAG = 0   

-- 偏移量
OFFSET_X, OFFSET_Y, OFFSET_Z = 0.0, 0.0, 0.0
OFFSET_RX, OFFSET_RY, OFFSET_RZ = 0.0, 0.0, 0.0

EX1, EX2, EX3, EX4 = 0.0, 0.0, 0.0, 0.0  

OACC = 100              
VEL_ACC_PARAM_MODE = 0  

print("机器人客户端启动...")

-- 初始轨迹
PTP(y放置移出点1,20,-1,0)
PTP(y抓取过渡点1,20,-1,0)
PTP(y抓取过渡点3,20,-1,0)
PTP(点4,20,-1,0)

while true do
    -- 1. 检查连接状态
    if tcp == 0 then
        print("尝试连接视觉服务端...")
        tcp = SocketOpen(VISION_IP, VISION_PORT, SOCKET_NAME)
        if tcp == 1 then
            print("连接成功")
        else
            WaitMs(1000)
        end

    -- 2. 已连接
    elseif tcp == 1 then
        -- 【优化】：在发送请求前增加一小段延时，给服务端留出呼吸时间
        -- 如果服务端计算很慢，可以把 200 改成 500 或 1000
        WaitMs(200) 

        local send_ret = SocketSendString("Need Pose", SOCKET_NAME, 0)
        if send_ret ~= 0 then
            print("发送失败，尝试重连")
            SocketClose(SOCKET_NAME)
            tcp = 0
        else
            -- 读取数据
            recv_str = SocketReadString(SOCKET_NAME, 0)

            if recv_str == nil or recv_str == "" or recv_str == "timeout" then
                if recv_str == "timeout" then
                    print("接收超时")
                    SocketClose(SOCKET_NAME)
                    tcp = 0
                else
                    print("收到空数据")
                    WaitMs(500)
                end
            elseif recv_str == "NO_POSE" then
                print("视觉暂无位姿，延长等待时间...")
                -- 【优化】：如果没有位姿，说明视觉还没算完，多等一会儿再进下一次循环
                WaitMs(1000) 
            else
                -- 只有确保 recv_str 是字符串，才执行 match
                x, y, rz = string.match(recv_str, "([%-%d%.]+)%s+([%-%d%.]+)%s+([%-%d%.]+)")

                if x and y and rz then
                    x  = tonumber(x)
                    y  = tonumber(y)
                    rz = tonumber(rz)

                    print(string.format("解析成功: X=%.2f, Y=%.2f, RZ=%.2f", x, y, rz))

                    -- 逆解与运动
                    j1,j2,j3,j4,j5,j6 = GetInverseKin(WORKPIECE_NUM, x, y, FIX_Z, FIX_RX, FIX_RY, rz, -1)

                    MoveL(
                        j1,j2,j3,j4,j5,j6, x, y, FIX_Z, FIX_RX, FIX_RY, rz,
                        TOOL_NUM, WORKPIECE_NUM, SPEED, ACC, OVL,
                        EX1, EX2, EX3, EX4, BLEND_R, SEARCH_FLAG, OFFSET_FLAG,
                        OFFSET_X, OFFSET_Y, OFFSET_Z, OFFSET_RX, OFFSET_RY, OFFSET_RZ,
                        OACC, VEL_ACC_PARAM_MODE
                    )

                    -- 动作逻辑
                    SetDO(0,1,0,1)
                    WaitMs(1500)

                    PTP(y抓取移出点1,20,-1,0)
                    PTP(y抓取过渡点5,20,-1,0)
                    PTP(y抓取过渡点3,20,-1,0)
                    PTP(y抓取过渡点1,20,-1,0)
                    PTP(y放置点1,20,-1,0)

                    SetDO(0,1,0,1)
                    WaitMs(1500)
                    PTP(y放置移出点1,20,-1,0)

                    -- 回到循环起始等待点
                    PTP(点4,20,-1,0)

                    -- 【关键】：完成一次完整动作后，视觉可能需要重新触发或清空缓存，建议多等一下
                    WaitMs(500)
                else
                    print("数据格式不匹配: " .. tostring(recv_str))
                    WaitMs(500)
                end
            end
        end
    end

    WaitMs(50) 
end