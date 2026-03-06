"""
runners.py — 本地编译和测试执行器
SmartRoute: Claude Code + Python 编排脚本整合方案

处理 MinGW/GCC 编译、测试脚本执行、乱码处理等本地操作
"""

import subprocess
import platform
import os
from typing import Tuple


def detect_encoding() -> str:
    """根据系统环境检测控制台编码"""
    if platform.system() == "Windows":
        return "gbk"  # Windows 中文环境默认 GBK
    return "utf-8"


def run_compile(project_dir: str, compile_command: str) -> Tuple[bool, str]:
    """
    执行本地编译

    Args:
        project_dir: 项目根目录
        compile_command: 编译命令 (如 "make -j4", "mingw32-make", "cmake --build build")

    Returns:
        (是否成功, 错误日志或成功信息)
    """
    encoding = detect_encoding()
    cmd_parts = compile_command.split()

    try:
        result = subprocess.run(
            cmd_parts,
            cwd=project_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding=encoding,
            errors="replace",  # 遇到无法解析的字符替换为 ?
            timeout=300,       # 编译超时 5 分钟
        )

        if result.returncode == 0:
            return True, result.stdout[-500:] if result.stdout else "编译成功"
        else:
            error_output = result.stderr + "\n" + result.stdout
            # 截取最后 2000 字符，避免日志过长撑爆上下文
            return False, error_output[-2000:]

    except subprocess.TimeoutExpired:
        return False, "[编译超时] 编译过程超过 300 秒，可能存在死循环或资源不足"
    except FileNotFoundError:
        return False, f"[编译命令未找到] 请确认 '{cmd_parts[0]}' 已安装并在 PATH 中"
    except Exception as e:
        return False, f"[编译异常] {str(e)}"


def run_tests(project_dir: str, test_command: str, timeout: int = 120) -> Tuple[str, str]:
    """
    执行测试脚本

    Args:
        project_dir: 项目根目录
        test_command: 测试命令
        timeout: 超时时间（秒）

    Returns:
        (结果状态, 详细日志)
        结果状态: "PASS" / "FAIL" / "FAIL_TIMEOUT" / "FAIL_EXECUTION"
    """
    encoding = detect_encoding()
    cmd_parts = test_command.split()

    try:
        result = subprocess.run(
            cmd_parts,
            cwd=project_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding=encoding,
            errors="replace",
            timeout=timeout,
        )

        full_output = result.stdout + "\n" + result.stderr

        if result.returncode == 0:
            return "PASS", full_output[-1000:]
        else:
            return "FAIL", full_output[-2000:]

    except subprocess.TimeoutExpired:
        return "FAIL_TIMEOUT", f"测试执行超时 ({timeout}秒)，可能存在死锁或死循环"
    except FileNotFoundError:
        return "FAIL_EXECUTION", f"测试命令未找到: '{cmd_parts[0]}'，请确认已编译并生成测试可执行文件"
    except Exception as e:
        return "FAIL_EXECUTION", f"测试执行异常: {str(e)}"


def read_file_safe(filepath: str, max_chars: int = 10000) -> str:
    """安全读取文件内容，截断过长的文件"""
    if not os.path.exists(filepath):
        return f"[文件不存在: {filepath}]"
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        if len(content) > max_chars:
            return content[:max_chars] + f"\n\n... [文件过长，已截断，总计 {len(content)} 字符]"
        return content
    except Exception as e:
        return f"[读取文件失败: {e}]"


def write_file_safe(filepath: str, content: str):
    """安全写入文件"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
