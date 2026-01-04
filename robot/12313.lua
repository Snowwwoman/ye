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

SPEED = 95       
ACC   = 90        
OVL   = 70        

BLEND_R = -1      
SEARCH_FLAG = 0   
OFFSET_FLAG = 0   

-- 偏移量
OFFSET_X, OFFSET_Y, OFFSET_Z = 0.0, 0.0, 0.0
OFFSET_RX, OFFSET_RY, OFFSET_RZ = 0.0, 0.0, 0.0

EX1, EX2, EX3, EX4 = 0.0, 0.0, 0.0, 0.0  

OACC = 100              
VEL_ACC_PARAM_MODE = 0  

-- 放置点计数器
put_count = 1
-- 存储下一个位姿
next_x, next_y, next_rz = nil, nil, nil

print("机器人客户端启动...")

-- 初始轨迹
PTP(y放置移出点1,20,-1,0)
PTP(y抓取过渡点1,20,-1,0)
PTP(y抓取过渡点3,20,-1,0)
PTP(点4,40,-1,0)

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
    end

    -- 2. 已连接
    if tcp == 1 then
        -- 如果有提前获取的位姿，直接使用
        local current_x, current_y, current_rz
        
        if next_x and next_y and next_rz then
            current_x, current_y, current_rz = next_x, next_y, next_rz
            next_x, next_y, next_rz = nil, nil, nil
            print("使用提前获取的位姿")
        else
            -- 请求新的位姿
            WaitMs(200)
            
            local send_ret = SocketSendString("Need Pose", SOCKET_NAME, 0)
            if send_ret ~= 0 then
                print("发送失败，尝试重连")
                SocketClose(SOCKET_NAME)
                tcp = 0
            else
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
                    WaitMs(9000) 
                else
                    current_x, current_y, current_rz = string.match(recv_str, "([%-%d%.]+)%s+([%-%d%.]+)%s+([%-%d%.]+)")
                    if current_x and current_y and current_rz then
                        current_x = tonumber(current_x)
                        current_y = tonumber(current_y)
                        current_rz = tonumber(current_rz)
                        print(string.format("解析成功: X=%.2f, Y=%.2f, RZ=%.2f", current_x, current_y, current_rz))
                    else
                        print("数据格式不匹配: " .. tostring(recv_str))
                        WaitMs(500)
                    end
                end
            end
        end
        
        -- 如果成功获取到位姿，执行抓取
        if current_x and current_y and current_rz then
            print(string.format("开始抓取: X=%.2f, Y=%.2f, RZ=%.2f", current_x, current_y, current_rz))
            
            -- 逆解与运动到抓取点
            j1,j2,j3,j4,j5,j6 = GetInverseKin(WORKPIECE_NUM, current_x, current_y, FIX_Z, FIX_RX, FIX_RY, current_rz, -1)
            
            MoveL(
                j1,j2,j3,j4,j5,j6, current_x, current_y, FIX_Z, FIX_RX, FIX_RY, current_rz,
                TOOL_NUM, WORKPIECE_NUM, SPEED, ACC, OVL,
                EX1, EX2, EX3, EX4, BLEND_R, SEARCH_FLAG, OFFSET_FLAG,
                OFFSET_X, OFFSET_Y, OFFSET_Z, OFFSET_RX, OFFSET_RY, OFFSET_RZ,
                OACC, VEL_ACC_PARAM_MODE
            )
            
            -- 抓取物体
            SetDO(0,1,0,1)
            WaitMs(1500)
            
            -- 移出抓取区域到点4
            PTP(y抓取移出点1,20,-1,0)
            PTP(y抓取过渡点5,20,-1,0)
            PTP(点4,20,-1,0)
            
            -- ========== 关键：在点4就发送下一个位姿请求 ==========
            print("在点4发送下一个位姿请求...")
            if tcp == 1 then
                local send_next = SocketSendString("Need Pose", SOCKET_NAME, 0)
                if send_next == 0 then
                    print("已发送下一个位姿请求")
                end
            end
            
            -- ========== 放置流程（轮流放置） ==========
            -- 移动到放置点（根据计数器选择）
            if put_count == 1 then
                PTP(put1,20,-1,0)
            elseif put_count == 2 then
                PTP(put2,20,-1,0)
            elseif put_count == 3 then
                PTP(put3,20,-1,0)
            elseif put_count == 4 then
                PTP(put4,20,-1,0)
            elseif put_count == 5 then
                PTP(put5,20,-1,0)
            end
            
            -- 放置物体
            SetDO(0,1,0,1)
            WaitMs(1500)
            
            
            
            -- 更新放置点计数器
            put_count = put_count + 1
            if put_count > 5 then
                put_count = 1
            end
            
            -- 返回等待点
            PTP(点4,20,-1,0)
            
            -- ========== 尝试读取下一个位姿 ==========
            print("尝试读取下一个位姿...")
            if tcp == 1 then
                local next_recv = SocketReadString(SOCKET_NAME, 0)
                if next_recv and next_recv ~= "" and next_recv ~= "timeout" and next_recv ~= "NO_POSE" then
                    local nx, ny, nrz = string.match(next_recv, "([%-%d%.]+)%s+([%-%d%.]+)%s+([%-%d%.]+)")
                    if nx and ny and nrz then
                        next_x = tonumber(nx)
                        next_y = tonumber(ny)
                        next_rz = tonumber(nrz)
                        print(string.format("成功获取下一个位姿: X=%.2f, Y=%.2f, RZ=%.2f", next_x, next_y, next_rz))
                    end
                else
                    print("尚未收到下一个位姿")
                end
            end
            
            WaitMs(500)
        else
            print("未获取到位姿，等待...")
            WaitMs(1000)
        end
    end

    WaitMs(50) 
end