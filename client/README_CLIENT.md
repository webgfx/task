# Task Client - Modular Architecture

## 概述

客户端已重构为模块化架构，将安装/卸载逻辑与启动/停止逻辑分离，实现更好的部署和更新体验。

## 架构说明

### 🏗️ 文件结构

```
client/
├── client_installer.py    # 安装/卸载/更新管理器
├── client_runner.py       # 运行时执行器
├── client.py             # 兼容性包装器 (已弃用)
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
   - 生成启动脚本

2. **client_runner.py** - 运行时执行器
   - 处理服务器通信
   - 执行任务
   - 系统信息收集
   - 心跳管理

3. **client.py** - 兼容性包装器（已弃用）
   - 提供向后兼容
   - 引导用户迁移到新架构

## 🚀 快速开始

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
├── client_runner.py      # 运行时执行器
├── executor.py           # 任务执行器
├── heartbeat.py          # 心跳管理器
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

### 配置文件 (config.json)

```json
{
  "server_url": "http://localhost:5000",
  "machine_name": "my-machine",
  "heartbeat_interval": 30,
  "config_update_interval": 600,
  "log_level": "INFO",
  "install_dir": "/home/user/.task_client",
  "log_dir": "/home/user/.task_client/logs",
  "work_dir": "/home/user/.task_client/work",
  "service_name": "task-client",
  "installed_at": "2025-01-01T12:00:00",
  "version": "1.0.0"
}
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
   - 确保使用 `client_runner.py` 而不是旧的 `client.py`
   - 检查安装目录中的文件是否完整

2. **权限问题**
   - 确保启动脚本有执行权限
   - Linux/Mac: `chmod +x ~/.task_client/start_client.sh`

3. **配置问题**
   - 使用 `python client_installer.py info` 检查配置
   - 手动编辑 `~/.task_client/config.json` 修正配置

## 🔄 从旧版本迁移

如果你使用的是旧版本的单文件客户端：

1. **停止旧客户端**
2. **安装新模块化客户端**:
   ```bash
   python client_installer.py install \
       --server-url YOUR_SERVER_URL \
       --machine-name YOUR_MACHINE_NAME
   ```
3. **使用新的启动方式**

旧的 `client.py` 仍然可用但会显示迁移提示。

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
