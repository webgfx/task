#!/usr/bin/env python3
"""
快速验证脚本 - 检查 Python 3.13 兼容性和关键功能
"""
import sys
import importlib
import requests
import time
from datetime import datetime

def check_python_version():
    """检查 Python 版本"""
    version = sys.version_info
    print(f"Python 版本: {version.major}.{version.minor}.{version.micro}")
    if version.major == 3 and version.minor >= 13:
        print("✅ Python 3.13+ 兼容")
    else:
        print("⚠️  不是 Python 3.13")
    return True

def check_imports():
    """检查关键模块导入"""
    modules = [
        ('flask', 'Flask web 框架'),
        ('flask_socketio', 'Flask-SocketIO WebSocket 支持'),
        ('gevent', 'Gevent 异步库'),
        ('psutil', '系统信息库'),
        ('requests', 'HTTP 客户端库'),
        ('apscheduler', '任务调度器'),
    ]
    
    success_count = 0
    for module_name, description in modules:
        try:
            module = importlib.import_module(module_name)
            version = getattr(module, '__version__', 'Unknown')
            print(f"✅ {description}: {module_name} v{version}")
            success_count += 1
        except ImportError as e:
            print(f"❌ {description}: 导入失败 - {e}")
    
    print(f"\n模块导入结果: {success_count}/{len(modules)} 成功")
    return success_count == len(modules)

def check_server_connection():
    """检查服务器连接"""
    server_url = "http://127.0.0.1:5000"
    
    try:
        # 测试基本连接
        response = requests.get(f"{server_url}/", timeout=5)
        if response.status_code == 200:
            print(f"✅ 服务器响应正常: {server_url}")
        else:
            print(f"⚠️  服务器响应状态码: {response.status_code}")
        
        # 测试 API 端点
        try:
            api_response = requests.get(f"{server_url}/api/machines", timeout=5)
            if api_response.status_code == 200:
                machines = api_response.json()
                print(f"✅ API 端点正常: 找到 {len(machines.get('data', []))} 台机器")
            else:
                print(f"⚠️  API 响应状态码: {api_response.status_code}")
        except Exception as e:
            print(f"❌ API 测试失败: {e}")
        
        return True
    except requests.ConnectionError:
        print(f"❌ 无法连接到服务器: {server_url}")
        print("   请确保服务器正在运行")
        return False
    except Exception as e:
        print(f"❌ 服务器连接测试失败: {e}")
        return False

def check_gevent_compatibility():
    """检查 gevent 与 Python 3.13 的兼容性"""
    try:
        import gevent
        import gevent.socket
        import gevent.event
        
        # 测试基本功能
        event = gevent.event.Event()
        event.set()
        
        if event.is_set():
            print(f"✅ Gevent {gevent.__version__} 功能正常")
            return True
        else:
            print("❌ Gevent 事件功能异常")
            return False
            
    except Exception as e:
        print(f"❌ Gevent 兼容性测试失败: {e}")
        return False

def main():
    """主函数"""
    print("=" * 60)
    print("Python 3.13 兼容性和功能验证")
    print("=" * 60)
    print(f"验证时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 执行所有检查
    checks = [
        ("Python 版本检查", check_python_version),
        ("模块导入检查", check_imports),
        ("Gevent 兼容性检查", check_gevent_compatibility),
        ("服务器连接检查", check_server_connection),
    ]
    
    results = []
    for check_name, check_func in checks:
        print(f"\n{'='*20} {check_name} {'='*20}")
        try:
            result = check_func()
            results.append((check_name, result))
        except Exception as e:
            print(f"❌ {check_name} 执行失败: {e}")
            results.append((check_name, False))
    
    # 总结结果
    print("\n" + "=" * 60)
    print("验证结果总结")
    print("=" * 60)
    
    success_count = 0
    for check_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{check_name}: {status}")
        if result:
            success_count += 1
    
    print(f"\n总体结果: {success_count}/{len(results)} 项检查通过")
    
    if success_count == len(results):
        print("🎉 所有检查都通过了！系统已经准备就绪。")
        return True
    else:
        print("⚠️  部分检查失败，请检查上述错误信息。")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
