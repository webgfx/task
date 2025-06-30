# Task Client - Modular Architecture

## 概述

客户端已重构为模块化架构，将安装/卸载逻辑与启动/停止逻辑分离，实现更好的部署和更新体验。

## 架构说明

### 🏗️ 文件结构

```
client/
├── client_installer.py    # 安装/卸载/更新管理器
├── client_runner.py       # 运行时执行器
├── client.cfg            # 客户端配置文件模板
├── config_manager.py     # 配置管理模块
├── config_tool.py        # 配置管理工具
├── quick_setup.sh        # Linux/Mac 快速安装脚本
├── quick_setup.bat       # Windows 快速安装脚本
├── executor.py           # 任务执行器
├── heartbeat.py          # 心跳管理器
└── README_CLIENT.md      # 本文档
```

### 🔧 组件说明

1. **client_installer.py** - 安装管理器
   - 一次性安装和配置
   - 更新核心文件（无需重新安装）
   - 卸载和清理
   - 生成启动脚本和配置文件

2. **client_runner.py** - 运行时执行器
   - 处理服务器通信
   - 执行任务
   - 系统信息收集
   - 心跳管理

3. **client.cfg** - 配置文件
   - 心跳频率配置
   - 日志级别设置
   - 网络参数调优
   - 性能和安全设置

4. **config_manager.py** - 配置管理模块
   - 配置文件读取和验证
   - 默认值管理
   - 配置项访问接口

5. **config_tool.py** - 配置管理工具
   - 交互式配置编辑
   - 配置验证和保存
   - 配置重置功能

## � 配置管理

### 配置文件说明

客户端使用两个配置文件：

1. **config.json** - 安装时生成的基本配置
2. **client.cfg** - 详细的运行时配置（可手动编辑）

### 心跳频率配置

心跳频率决定客户端向服务器发送存活信号的间隔，单位为秒。

**安装时设置:**
```bash
python client_installer.py install \
    --server-url http://localhost:5000 \
    --machine-name my-machine \
    --heartbeat-interval 60  # 60秒间隔
```

**安装后修改:**
```bash
# 方法1: 使用配置工具
python config_tool.py --heartbeat-interval 60 --save

# 方法2: 交互式配置
python config_tool.py --interactive

# 方法3: 直接编辑 client.cfg 文件
```

### 配置工具使用

**查看当前配置:**
```bash
python config_tool.py --show
```

**设置各种参数:**
```bash
# 设置心跳间隔为60秒
python config_tool.py --heartbeat-interval 60 --save

# 设置日志级别为DEBUG
python config_tool.py --log-level DEBUG --save

# 启用调试模式
python config_tool.py --debug-mode --save

# 设置WebSocket ping间隔
python config_tool.py --websocket-ping-interval 30 --save
```

**交互式配置模式:**
```bash
python config_tool.py --interactive
```

**验证配置:**
```bash
python config_tool.py --validate
```

### 配置项说明

| 配置项 | 默认值 | 说明 |
|--------|-------|------|
| `heartbeat_interval` | 30 | 心跳发送间隔（秒） |
| `config_update_interval` | 600 | 配置更新间隔（秒） |
| `log_level` | INFO | 日志级别（DEBUG/INFO/WARNING/ERROR） |
| `connection_timeout` | 10 | 连接超时时间（秒） |
| `websocket_ping_interval` | 25 | WebSocket ping间隔（秒） |
| `debug_mode` | false | 是否启用调试模式 |
| `max_concurrent_tasks` | 1 | 最大并发任务数 |

### 配置生效

配置修改后需要重启客户端才能生效：

```bash
# 停止客户端
~/.task_client/stop_client.sh

# 启动客户端
~/.task_client/start_client.sh
```

## �🚀 快速开始

### 方法 1: 使用快速安装脚本（推荐）

**Linux/Mac:**
```bash
./quick_setup.sh --server-url http://your-server:5000 --machine-name your-machine
```

**Windows:**
```cmd
quick_setup.bat --server-url http://your-server:5000 --machine-name your-machine
```

### 方法 2: 手动安装

#### 1. 安装客户端
```bash
python client_installer.py install \
    --server-url http://localhost:5000 \
    --machine-name my-machine
```

#### 2. 启动客户端
```bash
# 使用生成的启动脚本
~/.task_client/start_client.sh    # Linux/Mac
%USERPROFILE%\.task_client\start_client.bat    # Windows

# 或直接运行
python client_runner.py --config ~/.task_client/config.json
```

#### 3. 停止客户端
```bash
~/.task_client/stop_client.sh     # Linux/Mac
%USERPROFILE%\.task_client\stop_client.bat     # Windows
```

## 🔄 优势

### 🎯 模块化设计
- **分离关注点**: 安装逻辑与运行时逻辑完全分离
- **独立更新**: 可以只更新运行时文件，无需重新安装
- **清晰职责**: 每个组件有明确的责任边界

### 🚀 简化部署
- **一次安装**: 安装完成后生成标准启动脚本
- **标准化**: 跨平台一致的安装和运行体验
- **自动化**: 支持脚本化部署和管理

### 🔧 便捷维护
- **热更新**: 更新核心功能无需停机重装
- **版本管理**: 清晰的版本和配置管理
- **状态监控**: 内置状态检查和诊断工具

## 📋 使用说明

### 安装选项

```bash
python client_installer.py install \
    --server-url http://localhost:5000 \
    --machine-name my-machine \
    --heartbeat-interval 30 \
    --config-update-interval 600 \
    --log-level INFO \
    --install-dir ~/.task_client
```

### 配置管理

**查看当前配置:**
```bash
python config_tool.py --show
```

**设置心跳频率（秒）:**
```bash
python config_tool.py --heartbeat-interval 60 --save
```

**交互式配置:**
```bash
python config_tool.py --interactive
```

**验证配置:**
```bash
python config_tool.py --validate
```

### 管理命令

```bash
# 检查安装状态
python client_installer.py status

# 查看配置信息
python client_installer.py info

# 更新核心文件（不重新安装）
python client_installer.py update

# 卸载（保留数据）
python client_installer.py uninstall

# 完全卸载（删除所有数据）
python client_installer.py uninstall --remove-data
```

### 运行选项

```bash
# 使用配置文件运行
python client_runner.py --config ~/.task_client/config.json

# 覆盖日志级别
python client_runner.py --config ~/.task_client/config.json --log-level DEBUG
```

## 🗂️ 文件组织

### 安装目录结构 (~/.task_client)

```
.task_client/
├── config.json           # 主配置文件
├── client.cfg            # 客户端详细配置
├── client_runner.py      # 运行时执行器
├── executor.py           # 任务执行器
├── heartbeat.py          # 心跳管理器
├── config_manager.py     # 配置管理模块
├── common/               # 公共模块
│   ├── __init__.py
│   ├── config.py
│   ├── models.py
│   ├── system_info.py
│   └── utils.py
├── logs/                 # 日志目录
├── work/                 # 工作目录
│   └── task_results/     # 任务结果
├── start_client.bat      # Windows 启动脚本
├── stop_client.bat       # Windows 停止脚本
├── start_client.sh       # Linux/Mac 启动脚本
└── stop_client.sh        # Linux/Mac 停止脚本
```

### 配置文件 (client.cfg)

```ini
# Task Client Configuration File
[DEFAULT]
# 服务器连接设置
server_url = http://localhost:5000

# 客户端标识
machine_name = 

# 心跳设置（秒）
heartbeat_interval = 30

# 配置更新设置（秒）
config_update_interval = 600

# 日志设置
log_level = INFO

# 网络设置
connection_timeout = 10
reconnect_delay = 5

[ADVANCED]
# WebSocket 设置
websocket_ping_interval = 25
websocket_ping_timeout = 20

# 系统信息收集间隔（秒）
system_info_update_interval = 300

# 调试设置
debug_mode = false
verbose_logging = false

[PERFORMANCE]
# 性能调优设置
max_concurrent_tasks = 1
max_worker_threads = 4
```

## 🔄 更新流程

### 更新核心功能（推荐）
```bash
# 1. 停止客户端
~/.task_client/stop_client.sh

# 2. 更新核心文件
python client_installer.py update

# 3. 重新启动客户端
~/.task_client/start_client.sh
```

### 完整重新安装
```bash
# 1. 卸载现有安装
python client_installer.py uninstall

# 2. 重新安装
python client_installer.py install \
    --server-url http://localhost:5000 \
    --machine-name my-machine
```

## 🐛 故障排除

### 检查安装状态
```bash
python client_installer.py status
```

### 查看日志
```bash
# 实时日志
tail -f ~/.task_client/logs/client.log

# 查看配置
python client_installer.py info
```

### 常见问题

1. **模块导入错误**
   - 确保使用 `client_runner.py` 进行运行时执行
   - 检查安装目录中的文件是否完整

2. **权限问题**
   - 确保启动脚本有执行权限
   - Linux/Mac: `chmod +x ~/.task_client/start_client.sh`

3. **配置问题**
   - 使用 `python client_installer.py info` 检查配置
   - 手动编辑 `~/.task_client/config.json` 修正配置

## 🔄 从旧版本迁移

如果你使用的是旧版本的单文件客户端（client.py）：

1. **停止旧客户端**
2. **安装新模块化客户端**:
   ```bash
   python client_installer.py install \
       --server-url YOUR_SERVER_URL \
       --machine-name YOUR_MACHINE_NAME
   ```
3. **使用新的启动方式**

旧的单文件客户端已被完全替换为模块化架构。

## 🎯 最佳实践

1. **使用配置文件**: 避免在命令行中硬编码参数
2. **定期更新**: 使用 `python client_installer.py update` 获取最新功能
3. **监控日志**: 定期检查 `~/.task_client/logs/` 目录中的日志
4. **备份配置**: 重要部署前备份配置文件
5. **环境隔离**: 不同环境使用不同的机器名和配置

## 📝 注意事项

- 新架构与旧版服务器完全兼容
- 配置文件格式向后兼容
- 所有现有功能保持不变
- 支持所有现有的服务器 API
