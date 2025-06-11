#!/usr/bin/env python3
"""
文件长度检查工具 - 确保代码文件适合AI协同开发
适用于AstrBot SaaS项目，检查Python文件行数是否符合规范
"""

import os
import sys
from pathlib import Path
from typing import List, Tuple, Dict
import argparse
import json


def count_effective_lines(file_path: Path) -> int:
    """
    计算有效代码行数，排除空行和纯注释行
    
    Args:
        file_path: Python文件路径
        
    Returns:
        有效代码行数
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        # 处理编码问题
        with open(file_path, 'r', encoding='gbk') as f:
            lines = f.readlines()
    
    effective_lines = 0
    in_multiline_string = False
    string_delimiter = None
    
    for line in lines:
        stripped = line.strip()
        
        # 跳过空行
        if not stripped:
            continue
            
        # 检查多行字符串
        if '"""' in stripped or "'''" in stripped:
            if stripped.count('"""') % 2 == 1 or stripped.count("'''") % 2 == 1:
                in_multiline_string = not in_multiline_string
                string_delimiter = '"""' if '"""' in stripped else "'''"
            
        # 如果在多行字符串中，跳过
        if in_multiline_string:
            continue
            
        # 跳过纯注释行
        if stripped.startswith('#'):
            continue
            
        # 计算有效代码行
        effective_lines += 1
    
    return effective_lines


def analyze_file_complexity(file_path: Path) -> Dict[str, int]:
    """
    分析文件复杂度指标
    
    Args:
        file_path: Python文件路径
        
    Returns:
        复杂度指标字典
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        with open(file_path, 'r', encoding='gbk') as f:
            content = f.read()
    
    metrics = {
        'total_lines': len(content.splitlines()),
        'effective_lines': count_effective_lines(file_path),
        'classes': content.count('class '),
        'functions': content.count('def ') + content.count('async def '),
        'imports': content.count('import ') + content.count('from '),
    }
    
    return metrics


def check_directory_files(
    directory: str, 
    max_lines: int = 500,
    warning_threshold: float = 0.8,
    exclude_patterns: List[str] = None
) -> Tuple[List[str], List[str], List[Dict]]:
    """
    检查目录下所有Python文件的行数
    
    Args:
        directory: 要检查的目录路径
        max_lines: 最大行数限制
        warning_threshold: 警告阈值比例
        exclude_patterns: 排除的文件模式
        
    Returns:
        (警告列表, 错误列表, 详细分析列表)
    """
    if exclude_patterns is None:
        exclude_patterns = ['__pycache__', '.git', 'migrations', 'alembic/versions']
    
    warnings = []
    errors = []
    analysis = []
    
    warning_limit = int(max_lines * warning_threshold)
    
    for py_file in Path(directory).rglob("*.py"):
        # 跳过排除的文件
        if any(pattern in str(py_file) for pattern in exclude_patterns):
            continue
            
        # 跳过特殊文件
        if py_file.name.startswith("__") and py_file.name.endswith("__.py"):
            continue
            
        metrics = analyze_file_complexity(py_file)
        relative_path = py_file.relative_to(Path(directory).parent)
        
        analysis.append({
            'file': str(relative_path),
            'metrics': metrics
        })
        
        effective_lines = metrics['effective_lines']
        
        # 检查是否超过限制
        if effective_lines > max_lines:
            errors.append({
                'file': str(relative_path),
                'lines': effective_lines,
                'message': f"❌ {relative_path}: {effective_lines} 行 (超过 {max_lines} 行限制)",
                'suggestion': get_refactor_suggestion(py_file, metrics)
            })
        elif effective_lines > warning_limit:
            warnings.append({
                'file': str(relative_path),
                'lines': effective_lines,
                'message': f"⚠️ {relative_path}: {effective_lines} 行 (接近 {max_lines} 行限制)",
                'suggestion': "建议开始规划模块拆分"
            })
    
    return warnings, errors, analysis


def get_refactor_suggestion(file_path: Path, metrics: Dict[str, int]) -> str:
    """
    根据文件内容提供重构建议
    
    Args:
        file_path: 文件路径
        metrics: 文件复杂度指标
        
    Returns:
        重构建议
    """
    suggestions = []
    
    if metrics['classes'] > 3:
        suggestions.append("考虑将多个类拆分到不同文件")
    
    if metrics['functions'] > 20:
        suggestions.append("函数过多，考虑按功能分组到子模块")
    
    if 'service' in file_path.name.lower():
        suggestions.append("服务类建议按职责拆分：core、notification、analytics等")
    
    if 'router' in file_path.name.lower() or 'api' in file_path.name.lower():
        suggestions.append("API路由建议按资源类型拆分")
    
    if not suggestions:
        suggestions.append("建议按单一职责原则拆分功能模块")
    
    return "; ".join(suggestions)


def generate_report(warnings: List[Dict], errors: List[Dict], analysis: List[Dict], output_format: str = 'console'):
    """
    生成检查报告
    
    Args:
        warnings: 警告列表
        errors: 错误列表
        analysis: 详细分析列表
        output_format: 输出格式 ('console', 'json', 'markdown')
    """
    if output_format == 'console':
        print("🔍 文件长度检查报告")
        print("=" * 50)
        
        if errors:
            print(f"\n❌ 发现 {len(errors)} 个文件超过行数限制:")
            for error in errors:
                print(f"   {error['message']}")
                print(f"   💡 建议: {error['suggestion']}")
                print()
        
        if warnings:
            print(f"\n⚠️ 发现 {len(warnings)} 个文件接近行数限制:")
            for warning in warnings:
                print(f"   {warning['message']}")
                print(f"   💡 建议: {warning['suggestion']}")
                print()
        
        if not errors and not warnings:
            print("\n✅ 所有文件都符合行数规范！")
        
        # 统计信息
        total_files = len(analysis)
        avg_lines = sum(item['metrics']['effective_lines'] for item in analysis) / total_files if total_files > 0 else 0
        
        print(f"\n📊 统计信息:")
        print(f"   总文件数: {total_files}")
        print(f"   平均行数: {avg_lines:.1f}")
        print(f"   最大文件: {max(analysis, key=lambda x: x['metrics']['effective_lines'])['file'] if analysis else 'N/A'}")
        
    elif output_format == 'json':
        report = {
            'summary': {
                'total_files': len(analysis),
                'warnings': len(warnings),
                'errors': len(errors)
            },
            'warnings': warnings,
            'errors': errors,
            'analysis': analysis
        }
        print(json.dumps(report, indent=2, ensure_ascii=False))
    
    elif output_format == 'markdown':
        print("# 文件长度检查报告\n")
        
        if errors:
            print("## ❌ 超过限制的文件\n")
            for error in errors:
                print(f"- **{error['file']}**: {error['lines']} 行")
                print(f"  - 💡 {error['suggestion']}\n")
        
        if warnings:
            print("## ⚠️ 接近限制的文件\n")
            for warning in warnings:
                print(f"- **{warning['file']}**: {warning['lines']} 行")
                print(f"  - 💡 {warning['suggestion']}\n")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='检查Python文件行数是否符合AI协同开发规范')
    parser.add_argument('directory', help='要检查的目录路径')
    parser.add_argument('--max-lines', type=int, default=500, help='最大行数限制 (默认: 500)')
    parser.add_argument('--warning-threshold', type=float, default=0.8, help='警告阈值比例 (默认: 0.8)')
    parser.add_argument('--format', choices=['console', 'json', 'markdown'], default='console', help='输出格式')
    parser.add_argument('--exclude', nargs='*', default=['__pycache__', '.git', 'migrations', 'alembic/versions'], 
                       help='排除的目录模式')
    parser.add_argument('--ci', action='store_true', help='CI模式：发现错误时退出码为1')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.directory):
        print(f"❌ 错误: 目录 '{args.directory}' 不存在")
        sys.exit(1)
    
    # 执行检查
    warnings, errors, analysis = check_directory_files(
        args.directory,
        args.max_lines,
        args.warning_threshold,
        args.exclude
    )
    
    # 生成报告
    generate_report(warnings, errors, analysis, args.format)
    
    # CI模式：有错误时退出
    if args.ci and errors:
        sys.exit(1)


if __name__ == "__main__":
    main() 