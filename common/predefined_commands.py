"""
预定义指令管理模块
"""
import json
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

@dataclass
class PredefinedCommand:
    """预定义指令数据类"""
    id: int
    name: str
    command: str
    description: str = ""
    category: str = "general"
    timeout: int = 300
    requires_admin: bool = False
    target_os: List[str] = None  # ["windows", "linux", "macos"] 或 None 表示全平台
    
    def __post_init__(self):
        if self.target_os is None:
            self.target_os = []
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PredefinedCommand':
        return cls(**data)

class PredefinedCommandManager:
    """预定义指令管理器"""
    
    def __init__(self):
        self.commands: Dict[int, PredefinedCommand] = {}
        self._next_id = 1
        self._load_default_commands()
    
    def _load_default_commands(self):
        """加载默认预定义指令"""
        default_commands = [
            # 系统信息类
            PredefinedCommand(
                id=1, name="获取系统信息", 
                command="systeminfo", 
                description="获取详细的系统信息",
                category="system",
                target_os=["windows"]
            ),
            PredefinedCommand(
                id=2, name="获取系统信息(Linux)", 
                command="uname -a && cat /etc/os-release", 
                description="获取Linux系统信息",
                category="system",
                target_os=["linux"]
            ),
            PredefinedCommand(
                id=3, name="查看磁盘空间", 
                command="dir C:\\ /s /-c", 
                description="查看C盘磁盘使用情况",
                category="system",
                target_os=["windows"]
            ),
            PredefinedCommand(
                id=4, name="查看磁盘空间(Linux)", 
                command="df -h", 
                description="查看磁盘使用情况",
                category="system",
                target_os=["linux"]
            ),
            
            # 网络类
            PredefinedCommand(
                id=5, name="网络连接测试", 
                command="ping -n 4 8.8.8.8", 
                description="测试网络连接",
                category="network",
                target_os=["windows"]
            ),
            PredefinedCommand(
                id=6, name="网络连接测试(Linux)", 
                command="ping -c 4 8.8.8.8", 
                description="测试网络连接",
                category="network",
                target_os=["linux"]
            ),
            PredefinedCommand(
                id=7, name="查看网络配置", 
                command="ipconfig /all", 
                description="查看详细网络配置",
                category="network",
                target_os=["windows"]
            ),
            PredefinedCommand(
                id=8, name="查看网络配置(Linux)", 
                command="ip addr show", 
                description="查看网络配置",
                category="network",
                target_os=["linux"]
            ),
            
            # 进程管理类
            PredefinedCommand(
                id=9, name="查看进程列表", 
                command="tasklist", 
                description="查看运行中的进程",
                category="process",
                target_os=["windows"]
            ),
            PredefinedCommand(
                id=10, name="查看进程列表(Linux)", 
                command="ps aux", 
                description="查看运行中的进程",
                category="process",
                target_os=["linux"]
            ),
            
            # 文件操作类
            PredefinedCommand(
                id=11, name="列出目录内容", 
                command="dir", 
                description="列出当前目录内容",
                category="file",
                target_os=["windows"]
            ),
            PredefinedCommand(
                id=12, name="列出目录内容(Linux)", 
                command="ls -la", 
                description="列出当前目录内容",
                category="file",
                target_os=["linux"]
            ),
            
            # Python相关
            PredefinedCommand(
                id=13, name="Python版本检查", 
                command="python --version", 
                description="检查Python版本",
                category="development"
            ),
            PredefinedCommand(
                id=14, name="安装Python包", 
                command="pip install {package_name}", 
                description="安装指定的Python包（需要替换{package_name}）",
                category="development"
            ),
            
            # Git相关
            PredefinedCommand(
                id=15, name="Git状态检查", 
                command="git status", 
                description="检查Git仓库状态",
                category="development"
            ),
            PredefinedCommand(
                id=16, name="Git拉取更新", 
                command="git pull", 
                description="从远程仓库拉取最新代码",
                category="development"
            ),
            
            # 服务管理类
            PredefinedCommand(
                id=17, name="查看服务状态", 
                command="sc query", 
                description="查看Windows服务状态",
                category="service",
                target_os=["windows"],
                requires_admin=True
            ),
            PredefinedCommand(
                id=18, name="查看服务状态(Linux)", 
                command="systemctl list-units --type=service", 
                description="查看系统服务状态",
                category="service",
                target_os=["linux"]
            ),
        ]
        
        for cmd in default_commands:
            self.commands[cmd.id] = cmd
        
        self._next_id = max(self.commands.keys()) + 1 if self.commands else 1
        logger.info(f"Loaded {len(default_commands)} default predefined commands")
    
    def get_all_commands(self) -> List[PredefinedCommand]:
        """获取所有预定义指令"""
        return list(self.commands.values())
    
    def get_command(self, command_id: int) -> Optional[PredefinedCommand]:
        """根据ID获取指令"""
        return self.commands.get(command_id)
    
    def get_commands_by_category(self, category: str) -> List[PredefinedCommand]:
        """根据分类获取指令"""
        return [cmd for cmd in self.commands.values() if cmd.category == category]
    
    def get_commands_by_os(self, target_os: str) -> List[PredefinedCommand]:
        """根据操作系统获取指令"""
        return [cmd for cmd in self.commands.values() 
                if not cmd.target_os or target_os.lower() in [os.lower() for os in cmd.target_os]]
    
    def add_command(self, command: PredefinedCommand) -> int:
        """添加新指令"""
        if command.id and command.id in self.commands:
            raise ValueError(f"Command with ID {command.id} already exists")
        
        if not command.id:
            command.id = self._next_id
            self._next_id += 1
        
        self.commands[command.id] = command
        logger.info(f"Added new predefined command: {command.name} (ID: {command.id})")
        return command.id
    
    def update_command(self, command: PredefinedCommand):
        """更新指令"""
        if command.id not in self.commands:
            raise ValueError(f"Command with ID {command.id} does not exist")
        
        self.commands[command.id] = command
        logger.info(f"Updated predefined command: {command.name} (ID: {command.id})")
    
    def delete_command(self, command_id: int):
        """删除指令"""
        if command_id not in self.commands:
            raise ValueError(f"Command with ID {command_id} does not exist")
        
        cmd_name = self.commands[command_id].name
        del self.commands[command_id]
        logger.info(f"Deleted predefined command: {cmd_name} (ID: {command_id})")
    
    def get_categories(self) -> List[str]:
        """获取所有分类"""
        categories = set(cmd.category for cmd in self.commands.values())
        return sorted(list(categories))
    
    def search_commands(self, keyword: str) -> List[PredefinedCommand]:
        """搜索指令"""
        keyword = keyword.lower()
        results = []
        
        for cmd in self.commands.values():
            if (keyword in cmd.name.lower() or 
                keyword in cmd.description.lower() or 
                keyword in cmd.command.lower()):
                results.append(cmd)
        
        return results
    
    def export_commands(self) -> str:
        """导出指令为JSON"""
        commands_data = [cmd.to_dict() for cmd in self.commands.values()]
        return json.dumps(commands_data, indent=2, ensure_ascii=False)
    
    def import_commands(self, json_data: str):
        """从JSON导入指令"""
        try:
            commands_data = json.loads(json_data)
            imported_count = 0
            
            for cmd_data in commands_data:
                try:
                    command = PredefinedCommand.from_dict(cmd_data)
                    if command.id not in self.commands:
                        self.commands[command.id] = command
                        imported_count += 1
                        if command.id >= self._next_id:
                            self._next_id = command.id + 1
                except Exception as e:
                    logger.warning(f"Failed to import command: {cmd_data}. Error: {e}")
            
            logger.info(f"Imported {imported_count} predefined commands")
            return imported_count
            
        except Exception as e:
            logger.error(f"Failed to import commands from JSON: {e}")
            raise

# 全局预定义指令管理器实例
predefined_command_manager = PredefinedCommandManager()
