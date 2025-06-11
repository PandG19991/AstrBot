#!/usr/bin/env python3
"""
安全扫描脚本

自动化安全检查工具，检测AstrBot SaaS平台的安全漏洞：
1. SQL注入检测
2. XSS跨站脚本检测
3. 权限提升检测
4. 多租户隔离检测
5. API安全检测
6. 依赖漏洞扫描
7. 敏感信息泄露检测
"""
import asyncio
import aiohttp
import json
import re
import ssl
import subprocess
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional
from urllib.parse import urljoin
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SecurityScanner:
    """安全扫描器"""
    
    def __init__(self, base_url: str, auth_token: Optional[str] = None):
        """
        初始化安全扫描器
        
        Args:
            base_url: 目标服务器URL
            auth_token: 认证令牌
        """
        self.base_url = base_url.rstrip('/')
        self.auth_token = auth_token
        self.vulnerabilities = []
        self.scan_results = {
            "start_time": datetime.now(),
            "end_time": None,
            "total_tests": 0,
            "vulnerabilities_found": 0,
            "critical_issues": 0,
            "high_issues": 0,
            "medium_issues": 0,
            "low_issues": 0,
            "details": []
        }
    
    @property
    def headers(self) -> Dict[str, str]:
        """获取请求头"""
        headers = {
            "User-Agent": "SecurityScanner/1.0",
            "Content-Type": "application/json"
        }
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers
    
    async def run_security_scan(self) -> Dict[str, Any]:
        """运行完整的安全扫描"""
        logger.info("🔍 开始安全扫描...")
        
        async with aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=False),
            timeout=aiohttp.ClientTimeout(total=30)
        ) as session:
            
            # 运行所有安全检测
            await self.scan_sql_injection(session)
            await self.scan_xss_vulnerabilities(session)
            await self.scan_authentication_bypass(session)
            await self.scan_authorization_issues(session)
            await self.scan_multi_tenant_isolation(session)
            await self.scan_api_security(session)
            await self.scan_information_disclosure(session)
            await self.scan_rate_limiting(session)
            await self.scan_input_validation(session)
            await self.scan_cors_misconfiguration(session)
        
        # 运行静态安全检查
        await self.scan_dependencies()
        await self.scan_code_secrets()
        
        # 完成扫描
        self.scan_results["end_time"] = datetime.now()
        self.scan_results["total_tests"] = len(self.scan_results["details"])
        self.scan_results["vulnerabilities_found"] = len(self.vulnerabilities)
        
        # 统计漏洞严重程度
        for vuln in self.vulnerabilities:
            severity = vuln.get("severity", "low")
            if severity == "critical":
                self.scan_results["critical_issues"] += 1
            elif severity == "high":
                self.scan_results["high_issues"] += 1
            elif severity == "medium":
                self.scan_results["medium_issues"] += 1
            else:
                self.scan_results["low_issues"] += 1
        
        logger.info("✅ 安全扫描完成")
        return self.scan_results
    
    async def scan_sql_injection(self, session: aiohttp.ClientSession):
        """SQL注入检测"""
        logger.info("🔍 检测SQL注入漏洞...")
        
        # SQL注入测试载荷
        sql_payloads = [
            "' OR '1'='1",
            "'; DROP TABLE users; --",
            "' UNION SELECT * FROM users --",
            "1' AND (SELECT COUNT(*) FROM users) > 0 --",
            "'; WAITFOR DELAY '00:00:05' --",
            "' AND 1=1 --",
            "' AND 1=2 --",
            "admin'--",
            "admin' #",
            "admin'/*"
        ]
        
        # 测试端点
        test_endpoints = [
            "/api/v1/users",
            "/api/v1/sessions",
            "/api/v1/messages",
            "/api/v1/tenants"
        ]
        
        for endpoint in test_endpoints:
            for payload in sql_payloads:
                try:
                    # 测试查询参数注入
                    url = f"{self.base_url}{endpoint}?id={payload}"
                    async with session.get(url, headers=self.headers) as response:
                        await self._analyze_sql_injection_response(
                            response, endpoint, payload, "query_param"
                        )
                    
                    # 测试POST数据注入
                    test_data = {"id": payload, "name": payload}
                    async with session.post(
                        f"{self.base_url}{endpoint}",
                        json=test_data,
                        headers=self.headers
                    ) as response:
                        await self._analyze_sql_injection_response(
                            response, endpoint, payload, "post_data"
                        )
                        
                except Exception as e:
                    logger.warning(f"SQL注入测试异常: {endpoint} - {str(e)}")
    
    async def _analyze_sql_injection_response(
        self, 
        response: aiohttp.ClientResponse,
        endpoint: str,
        payload: str,
        injection_type: str
    ):
        """分析SQL注入响应"""
        try:
            text = await response.text()
            
            # SQL错误信息匹配
            sql_error_patterns = [
                r"ORA-\d{5}",  # Oracle
                r"MySQL.*Error",  # MySQL
                r"PostgreSQL.*ERROR",  # PostgreSQL
                r"Microsoft.*ODBC.*SQL",  # SQL Server
                r"SQLite.*error",  # SQLite
                r"syntax error.*near",
                r"unterminated quoted string",
                r"invalid input syntax",
                r"column.*does not exist"
            ]
            
            for pattern in sql_error_patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    vulnerability = {
                        "type": "SQL Injection",
                        "severity": "high",
                        "endpoint": endpoint,
                        "payload": payload,
                        "injection_type": injection_type,
                        "evidence": pattern,
                        "response_code": response.status,
                        "description": f"SQL错误信息泄露，可能存在SQL注入漏洞",
                        "recommendation": "使用参数化查询，验证输入数据"
                    }
                    self.vulnerabilities.append(vulnerability)
                    self._log_vulnerability(vulnerability)
                    break
                    
        except Exception as e:
            logger.warning(f"分析SQL注入响应异常: {str(e)}")
    
    async def scan_xss_vulnerabilities(self, session: aiohttp.ClientSession):
        """XSS跨站脚本检测"""
        logger.info("🔍 检测XSS漏洞...")
        
        # XSS测试载荷
        xss_payloads = [
            "<script>alert('XSS')</script>",
            "javascript:alert('XSS')",
            "<img src=x onerror=alert('XSS')>",
            "<svg/onload=alert('XSS')>",
            "';alert('XSS');//",
            "\"><script>alert('XSS')</script>",
            "<iframe src=javascript:alert('XSS')>",
            "<body onload=alert('XSS')>",
            "<input autofocus onfocus=alert('XSS')>",
            "javascript:/*--></title></style></textarea></script></xmp>"
        ]
        
        # 测试端点
        test_endpoints = [
            "/api/v1/messages",
            "/api/v1/sessions",
            "/api/v1/users"
        ]
        
        for endpoint in test_endpoints:
            for payload in xss_payloads:
                try:
                    # 测试POST数据XSS
                    test_data = {
                        "content": payload,
                        "message": payload,
                        "description": payload
                    }
                    
                    async with session.post(
                        f"{self.base_url}{endpoint}",
                        json=test_data,
                        headers=self.headers
                    ) as response:
                        await self._analyze_xss_response(
                            response, endpoint, payload
                        )
                        
                except Exception as e:
                    logger.warning(f"XSS测试异常: {endpoint} - {str(e)}")
    
    async def _analyze_xss_response(
        self,
        response: aiohttp.ClientResponse,
        endpoint: str,
        payload: str
    ):
        """分析XSS响应"""
        try:
            text = await response.text()
            
            # 检查是否原样返回了XSS载荷
            if payload in text and "<script>" in payload:
                vulnerability = {
                    "type": "Cross-Site Scripting (XSS)",
                    "severity": "medium",
                    "endpoint": endpoint,
                    "payload": payload,
                    "response_code": response.status,
                    "description": "输入内容未经适当过滤直接输出，存在XSS风险",
                    "recommendation": "对用户输入进行HTML转义，使用CSP策略"
                }
                self.vulnerabilities.append(vulnerability)
                self._log_vulnerability(vulnerability)
                
        except Exception as e:
            logger.warning(f"分析XSS响应异常: {str(e)}")
    
    async def scan_authentication_bypass(self, session: aiohttp.ClientSession):
        """认证绕过检测"""
        logger.info("🔍 检测认证绕过漏洞...")
        
        # 需要认证的端点
        protected_endpoints = [
            "/api/v1/users",
            "/api/v1/sessions",
            "/api/v1/messages", 
            "/api/v1/analytics",
            "/api/v1/ai/auto-reply"
        ]
        
        for endpoint in protected_endpoints:
            try:
                # 测试无token访问
                headers_no_auth = {"Content-Type": "application/json"}
                async with session.get(
                    f"{self.base_url}{endpoint}",
                    headers=headers_no_auth
                ) as response:
                    if response.status == 200:
                        vulnerability = {
                            "type": "Authentication Bypass",
                            "severity": "critical",
                            "endpoint": endpoint,
                            "response_code": response.status,
                            "description": "受保护的端点可以在无认证情况下访问",
                            "recommendation": "确保所有受保护端点都需要有效认证"
                        }
                        self.vulnerabilities.append(vulnerability)
                        self._log_vulnerability(vulnerability)
                
                # 测试无效token
                headers_invalid = {
                    "Content-Type": "application/json",
                    "Authorization": "Bearer invalid_token_12345"
                }
                async with session.get(
                    f"{self.base_url}{endpoint}",
                    headers=headers_invalid
                ) as response:
                    if response.status == 200:
                        vulnerability = {
                            "type": "Authentication Bypass",
                            "severity": "critical",
                            "endpoint": endpoint,
                            "response_code": response.status,
                            "description": "无效token可以访问受保护端点",
                            "recommendation": "加强token验证逻辑"
                        }
                        self.vulnerabilities.append(vulnerability)
                        self._log_vulnerability(vulnerability)
                        
            except Exception as e:
                logger.warning(f"认证绕过测试异常: {endpoint} - {str(e)}")
    
    async def scan_authorization_issues(self, session: aiohttp.ClientSession):
        """权限提升检测"""
        logger.info("🔍 检测权限提升漏洞...")
        
        # 测试IDOR (不安全的直接对象引用)
        idor_endpoints = [
            "/api/v1/users/",
            "/api/v1/sessions/",
            "/api/v1/messages/",
            "/api/v1/tenants/"
        ]
        
        # 测试访问其他用户的资源
        test_ids = ["1", "2", "999", "admin", "../", "../../etc/passwd"]
        
        for endpoint in idor_endpoints:
            for test_id in test_ids:
                try:
                    url = f"{self.base_url}{endpoint}{test_id}"
                    async with session.get(url, headers=self.headers) as response:
                        if response.status == 200:
                            text = await response.text()
                            if "id" in text and "email" in text:
                                vulnerability = {
                                    "type": "Insecure Direct Object Reference (IDOR)",
                                    "severity": "high",
                                    "endpoint": endpoint,
                                    "test_id": test_id,
                                    "response_code": response.status,
                                    "description": "可能可以访问其他用户的敏感数据",
                                    "recommendation": "实施适当的权限检查和用户数据隔离"
                                }
                                self.vulnerabilities.append(vulnerability)
                                self._log_vulnerability(vulnerability)
                                
                except Exception as e:
                    logger.warning(f"权限测试异常: {endpoint}{test_id} - {str(e)}")
    
    async def scan_multi_tenant_isolation(self, session: aiohttp.ClientSession):
        """多租户隔离检测"""
        logger.info("🔍 检测多租户隔离漏洞...")
        
        # 测试跨租户数据访问
        tenant_endpoints = [
            "/api/v1/sessions",
            "/api/v1/messages",
            "/api/v1/users"
        ]
        
        # 模拟不同租户ID
        tenant_ids = ["tenant1", "tenant2", "../", "null", "admin"]
        
        for endpoint in tenant_endpoints:
            for tenant_id in tenant_ids:
                try:
                    headers = self.headers.copy()
                    headers["X-Tenant-ID"] = tenant_id
                    
                    async with session.get(
                        f"{self.base_url}{endpoint}",
                        headers=headers
                    ) as response:
                        if response.status == 200:
                            text = await response.text()
                            if "items" in text or "data" in text:
                                vulnerability = {
                                    "type": "Multi-Tenant Isolation Bypass",
                                    "severity": "critical",
                                    "endpoint": endpoint,
                                    "tenant_id": tenant_id,
                                    "response_code": response.status,
                                    "description": "可能可以访问其他租户的数据",
                                    "recommendation": "加强租户隔离验证，确保数据访问控制"
                                }
                                self.vulnerabilities.append(vulnerability)
                                self._log_vulnerability(vulnerability)
                                
                except Exception as e:
                    logger.warning(f"多租户测试异常: {endpoint} - {str(e)}")
    
    async def scan_api_security(self, session: aiohttp.ClientSession):
        """API安全检测"""
        logger.info("🔍 检测API安全问题...")
        
        # 检测HTTP方法
        test_endpoints = [
            "/api/v1/health",
            "/api/v1/sessions",
            "/api/v1/messages"
        ]
        
        dangerous_methods = ["TRACE", "OPTIONS", "PUT", "DELETE"]
        
        for endpoint in test_endpoints:
            for method in dangerous_methods:
                try:
                    async with session.request(
                        method,
                        f"{self.base_url}{endpoint}",
                        headers=self.headers
                    ) as response:
                        if response.status in [200, 204]:
                            vulnerability = {
                                "type": "Unsafe HTTP Method",
                                "severity": "low",
                                "endpoint": endpoint,
                                "method": method,
                                "response_code": response.status,
                                "description": f"端点支持可能不安全的HTTP方法: {method}",
                                "recommendation": "限制不必要的HTTP方法"
                            }
                            self.vulnerabilities.append(vulnerability)
                            self._log_vulnerability(vulnerability)
                            
                except Exception as e:
                    logger.warning(f"API方法测试异常: {method} {endpoint} - {str(e)}")
    
    async def scan_information_disclosure(self, session: aiohttp.ClientSession):
        """信息泄露检测"""
        logger.info("🔍 检测信息泄露...")
        
        # 测试错误信息泄露
        error_endpoints = [
            "/api/v1/nonexistent",
            "/api/v1/users/99999999",
            "/api/v1/sessions/invalid-uuid"
        ]
        
        for endpoint in error_endpoints:
            try:
                async with session.get(
                    f"{self.base_url}{endpoint}",
                    headers=self.headers
                ) as response:
                    text = await response.text()
                    
                    # 检测敏感信息泄露
                    sensitive_patterns = [
                        r"File \".*\.py\"",  # Python文件路径
                        r"Traceback \(most recent call last\)",  # Python堆栈跟踪
                        r"at.*\.java:\d+",  # Java堆栈跟踪
                        r"Database.*error",  # 数据库错误
                        r"password.*=.*['\"]",  # 密码泄露
                        r"token.*=.*['\"]",  # Token泄露
                        r"secret.*=.*['\"]",  # 密钥泄露
                        r"/home/.*",  # 文件路径
                        r"root@.*"  # 系统用户
                    ]
                    
                    for pattern in sensitive_patterns:
                        if re.search(pattern, text, re.IGNORECASE):
                            vulnerability = {
                                "type": "Information Disclosure",
                                "severity": "medium",
                                "endpoint": endpoint,
                                "pattern": pattern,
                                "response_code": response.status,
                                "description": "错误响应可能泄露敏感系统信息",
                                "recommendation": "使用通用错误消息，避免泄露技术细节"
                            }
                            self.vulnerabilities.append(vulnerability)
                            self._log_vulnerability(vulnerability)
                            break
                            
            except Exception as e:
                logger.warning(f"信息泄露测试异常: {endpoint} - {str(e)}")
    
    async def scan_rate_limiting(self, session: aiohttp.ClientSession):
        """速率限制检测"""
        logger.info("🔍 检测速率限制...")
        
        # 测试端点
        test_endpoint = "/api/v1/health"
        
        # 快速发送多个请求
        request_count = 100
        successful_requests = 0
        
        for i in range(request_count):
            try:
                async with session.get(
                    f"{self.base_url}{test_endpoint}",
                    headers=self.headers
                ) as response:
                    if response.status == 200:
                        successful_requests += 1
                        
            except Exception as e:
                logger.warning(f"速率限制测试异常: {str(e)}")
        
        # 如果所有请求都成功，可能缺少速率限制
        if successful_requests >= request_count * 0.9:  # 90%以上成功
            vulnerability = {
                "type": "Missing Rate Limiting",
                "severity": "medium",
                "endpoint": test_endpoint,
                "successful_requests": successful_requests,
                "total_requests": request_count,
                "description": "端点可能缺少速率限制保护",
                "recommendation": "实施API速率限制防止滥用"
            }
            self.vulnerabilities.append(vulnerability)
            self._log_vulnerability(vulnerability)
    
    async def scan_input_validation(self, session: aiohttp.ClientSession):
        """输入验证检测"""
        logger.info("🔍 检测输入验证问题...")
        
        # 测试超长输入
        long_string = "A" * 10000
        
        test_data = {
            "name": long_string,
            "email": long_string + "@test.com",
            "content": long_string,
            "description": long_string
        }
        
        test_endpoints = [
            "/api/v1/users",
            "/api/v1/messages",
            "/api/v1/sessions"
        ]
        
        for endpoint in test_endpoints:
            try:
                async with session.post(
                    f"{self.base_url}{endpoint}",
                    json=test_data,
                    headers=self.headers
                ) as response:
                    if response.status == 500:
                        vulnerability = {
                            "type": "Input Validation Issue",
                            "severity": "medium",
                            "endpoint": endpoint,
                            "response_code": response.status,
                            "description": "超长输入导致服务器错误",
                            "recommendation": "实施输入长度验证"
                        }
                        self.vulnerabilities.append(vulnerability)
                        self._log_vulnerability(vulnerability)
                        
            except Exception as e:
                logger.warning(f"输入验证测试异常: {endpoint} - {str(e)}")
    
    async def scan_cors_misconfiguration(self, session: aiohttp.ClientSession):
        """CORS配置检测"""
        logger.info("🔍 检测CORS配置问题...")
        
        # 测试恶意Origin
        malicious_origins = [
            "http://evil.com",
            "https://attacker.com",
            "null",
            "*"
        ]
        
        for origin in malicious_origins:
            try:
                headers = self.headers.copy()
                headers["Origin"] = origin
                
                async with session.options(
                    f"{self.base_url}/api/v1/health",
                    headers=headers
                ) as response:
                    cors_header = response.headers.get("Access-Control-Allow-Origin")
                    if cors_header and (cors_header == origin or cors_header == "*"):
                        vulnerability = {
                            "type": "CORS Misconfiguration",
                            "severity": "medium",
                            "origin": origin,
                            "cors_header": cors_header,
                            "description": "CORS配置过于宽松，可能允许恶意跨域请求",
                            "recommendation": "限制CORS只允许可信域名"
                        }
                        self.vulnerabilities.append(vulnerability)
                        self._log_vulnerability(vulnerability)
                        
            except Exception as e:
                logger.warning(f"CORS测试异常: {origin} - {str(e)}")
    
    async def scan_dependencies(self):
        """依赖漏洞扫描"""
        logger.info("🔍 扫描依赖漏洞...")
        
        try:
            # 运行safety检查Python依赖
            result = subprocess.run(
                ["safety", "check", "--json"],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                vulnerabilities = json.loads(result.stdout)
                for vuln in vulnerabilities:
                    vulnerability = {
                        "type": "Vulnerable Dependency",
                        "severity": "high",
                        "package": vuln.get("package"),
                        "version": vuln.get("installed_version"),
                        "vulnerability": vuln.get("vulnerability"),
                        "description": vuln.get("advisory"),
                        "recommendation": "升级到安全版本"
                    }
                    self.vulnerabilities.append(vulnerability)
                    self._log_vulnerability(vulnerability)
                    
        except subprocess.TimeoutExpired:
            logger.warning("依赖扫描超时")
        except FileNotFoundError:
            logger.warning("safety工具未安装，跳过依赖扫描")
        except Exception as e:
            logger.warning(f"依赖扫描异常: {str(e)}")
    
    async def scan_code_secrets(self):
        """代码密钥扫描"""
        logger.info("🔍 扫描代码中的密钥...")
        
        try:
            # 运行truffleHog或自定义密钥检测
            secret_patterns = [
                (r"password\s*=\s*['\"][^'\"]+['\"]", "硬编码密码"),
                (r"api_key\s*=\s*['\"][^'\"]+['\"]", "硬编码API密钥"),
                (r"secret_key\s*=\s*['\"][^'\"]+['\"]", "硬编码密钥"),
                (r"jwt_secret\s*=\s*['\"][^'\"]+['\"]", "硬编码JWT密钥"),
                (r"database_url\s*=\s*['\"][^'\"]+['\"]", "硬编码数据库URL"),
                (r"redis_url\s*=\s*['\"][^'\"]+['\"]", "硬编码Redis URL")
            ]
            
            # 扫描代码文件
            import os
            for root, dirs, files in os.walk("."):
                # 跳过隐藏目录和常见的非代码目录
                dirs[:] = [d for d in dirs if not d.startswith('.') 
                          and d not in ['__pycache__', 'node_modules', 'venv']]
                
                for file in files:
                    if file.endswith(('.py', '.js', '.ts', '.yml', '.yaml', '.json')):
                        file_path = os.path.join(root, file)
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                                
                            for pattern, description in secret_patterns:
                                matches = re.finditer(pattern, content, re.IGNORECASE)
                                for match in matches:
                                    vulnerability = {
                                        "type": "Hardcoded Secret",
                                        "severity": "high",
                                        "file": file_path,
                                        "line": content[:match.start()].count('\n') + 1,
                                        "pattern": description,
                                        "description": f"在代码中发现{description}",
                                        "recommendation": "使用环境变量或密钥管理服务"
                                    }
                                    self.vulnerabilities.append(vulnerability)
                                    self._log_vulnerability(vulnerability)
                                    
                        except (UnicodeDecodeError, IOError):
                            continue
                            
        except Exception as e:
            logger.warning(f"密钥扫描异常: {str(e)}")
    
    def _log_vulnerability(self, vulnerability: Dict[str, Any]):
        """记录漏洞"""
        severity = vulnerability.get("severity", "low")
        vuln_type = vulnerability.get("type", "Unknown")
        
        # 根据严重程度使用不同日志级别
        if severity == "critical":
            logger.error(f"🚨 CRITICAL: {vuln_type}")
        elif severity == "high":
            logger.warning(f"⚠️  HIGH: {vuln_type}")
        elif severity == "medium":
            logger.info(f"📋 MEDIUM: {vuln_type}")
        else:
            logger.debug(f"ℹ️  LOW: {vuln_type}")
        
        # 添加到扫描结果
        self.scan_results["details"].append(vulnerability)
    
    def generate_report(self, output_file: str = "security_report.json"):
        """生成安全报告"""
        logger.info(f"📄 生成安全报告: {output_file}")
        
        # 生成摘要
        summary = {
            "scan_summary": self.scan_results,
            "vulnerabilities": self.vulnerabilities,
            "recommendations": self._generate_recommendations()
        }
        
        # 保存JSON报告
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False, default=str)
        
        # 生成HTML报告
        html_file = output_file.replace('.json', '.html')
        self._generate_html_report(summary, html_file)
        
        logger.info(f"✅ 报告已生成: {output_file}, {html_file}")
    
    def _generate_recommendations(self) -> List[str]:
        """生成安全建议"""
        recommendations = []
        
        # 基于发现的漏洞类型生成建议
        vuln_types = set(v.get("type") for v in self.vulnerabilities)
        
        if "SQL Injection" in vuln_types:
            recommendations.append("实施参数化查询，避免SQL注入")
        
        if "Cross-Site Scripting (XSS)" in vuln_types:
            recommendations.append("对用户输入进行HTML转义，实施CSP策略")
        
        if "Authentication Bypass" in vuln_types:
            recommendations.append("加强认证机制，确保所有受保护端点都需要认证")
        
        if "Multi-Tenant Isolation Bypass" in vuln_types:
            recommendations.append("强化多租户隔离，确保数据访问控制")
        
        if "Information Disclosure" in vuln_types:
            recommendations.append("使用通用错误消息，避免泄露技术细节")
        
        if "Vulnerable Dependency" in vuln_types:
            recommendations.append("定期更新依赖包到安全版本")
        
        if "Hardcoded Secret" in vuln_types:
            recommendations.append("使用环境变量或密钥管理服务存储敏感信息")
        
        # 通用安全建议
        recommendations.extend([
            "实施HTTPS加密传输",
            "配置适当的安全头（HSTS, CSP等）",
            "定期进行安全审计和渗透测试",
            "实施监控和日志记录",
            "建立安全事件响应流程"
        ])
        
        return recommendations
    
    def _generate_html_report(self, summary: Dict[str, Any], output_file: str):
        """生成HTML格式报告"""
        html_content = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AstrBot SaaS 安全扫描报告</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; background-color: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        h1, h2, h3 {{ color: #333; }}
        .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 20px 0; }}
        .stat-card {{ background: #f8f9fa; padding: 20px; border-radius: 8px; text-align: center; border-left: 4px solid #007bff; }}
        .critical {{ border-left-color: #dc3545; }}
        .high {{ border-left-color: #fd7e14; }}
        .medium {{ border-left-color: #ffc107; }}
        .low {{ border-left-color: #28a745; }}
        .vulnerability {{ background: #f8f9fa; margin: 10px 0; padding: 15px; border-radius: 8px; border-left: 4px solid #6c757d; }}
        .vulnerability.critical {{ border-left-color: #dc3545; background: #f8d7da; }}
        .vulnerability.high {{ border-left-color: #fd7e14; background: #fff3cd; }}
        .vulnerability.medium {{ border-left-color: #ffc107; background: #fff3cd; }}
        .vulnerability.low {{ border-left-color: #28a745; background: #d4edda; }}
        .timestamp {{ color: #6c757d; font-size: 0.9em; }}
        ul {{ list-style-type: none; padding-left: 0; }}
        li {{ background: #e9ecef; margin: 5px 0; padding: 10px; border-radius: 5px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🔍 AstrBot SaaS 安全扫描报告</h1>
        <p class="timestamp">扫描时间: {summary['scan_summary']['start_time']} - {summary['scan_summary']['end_time']}</p>
        
        <h2>📊 扫描摘要</h2>
        <div class="summary">
            <div class="stat-card">
                <h3>总测试数</h3>
                <h2>{summary['scan_summary']['total_tests']}</h2>
            </div>
            <div class="stat-card critical">
                <h3>严重漏洞</h3>
                <h2>{summary['scan_summary']['critical_issues']}</h2>
            </div>
            <div class="stat-card high">
                <h3>高危漏洞</h3>
                <h2>{summary['scan_summary']['high_issues']}</h2>
            </div>
            <div class="stat-card medium">
                <h3>中危漏洞</h3>
                <h2>{summary['scan_summary']['medium_issues']}</h2>
            </div>
            <div class="stat-card low">
                <h3>低危漏洞</h3>
                <h2>{summary['scan_summary']['low_issues']}</h2>
            </div>
        </div>
        
        <h2>🚨 发现的漏洞</h2>
        {''.join([f'<div class="vulnerability {v.get("severity", "low")}"><h3>{v.get("type", "Unknown")}</h3><p><strong>严重程度:</strong> {v.get("severity", "low").upper()}</p><p><strong>描述:</strong> {v.get("description", "")}</p><p><strong>建议:</strong> {v.get("recommendation", "")}</p></div>' for v in summary['vulnerabilities']])}
        
        <h2>💡 安全建议</h2>
        <ul>
            {''.join([f'<li>{rec}</li>' for rec in summary['recommendations']])}
        </ul>
    </div>
</body>
</html>
        """
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)


async def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="AstrBot SaaS 安全扫描工具")
    parser.add_argument("--url", default="http://localhost:8000", help="目标URL")
    parser.add_argument("--token", help="认证Token")
    parser.add_argument("--output", default="security_report.json", help="输出文件")
    
    args = parser.parse_args()
    
    # 创建扫描器并运行扫描
    scanner = SecurityScanner(args.url, args.token)
    results = await scanner.run_security_scan()
    
    # 生成报告
    scanner.generate_report(args.output)
    
    # 打印扫描结果摘要
    print("\n" + "="*60)
    print("🔍 AstrBot SaaS 安全扫描完成")
    print("="*60)
    print(f"📊 总测试数: {results['total_tests']}")
    print(f"🚨 发现漏洞: {results['vulnerabilities_found']}")
    print(f"   - 严重: {results['critical_issues']}")
    print(f"   - 高危: {results['high_issues']}")
    print(f"   - 中危: {results['medium_issues']}")
    print(f"   - 低危: {results['low_issues']}")
    print(f"📄 报告已保存到: {args.output}")
    print("="*60)
    
    # 如果发现严重漏洞，退出码为1
    if results['critical_issues'] > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main()) 