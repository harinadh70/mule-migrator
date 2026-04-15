"""
Tests for generated Spring Boot Configuration classes — validates
@Configuration, @Bean annotations, and correct conditional generation
of JmsConfig, AmqpConfig, KafkaConfig, SecurityConfig, CacheConfig,
RestTemplateConfig, WebClientConfig, AsyncConfig, SftpConfig, S3Config,
SqsConfig, CorsConfig, etc.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
_OLD_SETUP = str(Path(_PROJECT_ROOT) / "OLD-local-setup")
for p in (_PROJECT_ROOT, _OLD_SETUP):
    if p not in sys.path:
        sys.path.insert(0, p)

from backend.migrator.spring_generator import SpringBootGenerator


@pytest.fixture
def gen():
    return SpringBootGenerator("test-app", "com.example", "17")


# ═══════════════════════════════════════════════════════════════════
#  Scheduling Config
# ═══════════════════════════════════════════════════════════════════

class TestSchedulingConfig:
    def test_has_configuration_annotation(self, gen):
        code = gen._gen_scheduling_config()
        assert "@Configuration" in code

    def test_has_package_declaration(self, gen):
        code = gen._gen_scheduling_config()
        assert "package com.example.config;" in code

    def test_class_name(self, gen):
        code = gen._gen_scheduling_config()
        assert "public class SchedulingConfig" in code

    def test_enable_scheduling_import(self, gen):
        code = gen._gen_scheduling_config()
        assert "EnableScheduling" in code


# ═══════════════════════════════════════════════════════════════════
#  JMS Config
# ═══════════════════════════════════════════════════════════════════

class TestJmsConfig:
    def test_has_configuration_annotation(self, gen):
        code = gen._gen_jms_config()
        assert "@Configuration" in code

    def test_class_name(self, gen):
        code = gen._gen_jms_config()
        assert "public class JmsConfig" in code

    def test_enable_jms_import(self, gen):
        code = gen._gen_jms_config()
        assert "EnableJms" in code


# ═══════════════════════════════════════════════════════════════════
#  AMQP Config
# ═══════════════════════════════════════════════════════════════════

class TestAmqpConfig:
    def test_has_configuration_annotation(self, gen):
        code = gen._gen_amqp_config()
        assert "@Configuration" in code

    def test_class_name(self, gen):
        code = gen._gen_amqp_config()
        assert "public class AmqpConfig" in code

    def test_enable_rabbit_import(self, gen):
        code = gen._gen_amqp_config()
        assert "EnableRabbit" in code


# ═══════════════════════════════════════════════════════════════════
#  Kafka Config
# ═══════════════════════════════════════════════════════════════════

class TestKafkaConfig:
    def test_has_configuration_annotation(self, gen):
        code = gen._gen_kafka_config()
        assert "@Configuration" in code

    def test_class_name(self, gen):
        code = gen._gen_kafka_config()
        assert "public class KafkaConfig" in code

    def test_enable_kafka_import(self, gen):
        code = gen._gen_kafka_config()
        assert "EnableKafka" in code


# ═══════════════════════════════════════════════════════════════════
#  RestTemplate Config
# ═══════════════════════════════════════════════════════════════════

class TestRestTemplateConfig:
    def test_has_bean_annotation(self, gen):
        code = gen._gen_rest_template_config()
        assert "@Bean" in code

    def test_returns_rest_template(self, gen):
        code = gen._gen_rest_template_config()
        assert "RestTemplate" in code
        assert "return new" in code

    def test_method_name(self, gen):
        code = gen._gen_rest_template_config()
        assert "restTemplate()" in code


# ═══════════════════════════════════════════════════════════════════
#  WebClient Config
# ═══════════════════════════════════════════════════════════════════

class TestWebClientConfig:
    def test_has_bean_annotation(self, gen):
        code = gen._gen_webclient_config({"global_configs": []})
        assert "@Bean" in code

    def test_webclient_builder(self, gen):
        code = gen._gen_webclient_config({"global_configs": []})
        assert "WebClient.Builder" in code or "webClientBuilder" in code

    def test_named_bean_for_http_request_config(self, gen):
        parsed = {"global_configs": [{
            "type": "http-request",
            "name": "External-API",
            "host": "api.example.com",
            "port": "443",
            "protocol": "HTTPS",
            "basePath": "/v2",
        }]}
        code = gen._gen_webclient_config(parsed)
        assert "api.example.com" in code
        assert "WebClient" in code
        assert "@Bean" in code


# ═══════════════════════════════════════════════════════════════════
#  Cache Config
# ═══════════════════════════════════════════════════════════════════

class TestCacheConfig:
    def test_has_configuration_annotation(self, gen):
        code = gen._gen_cache_config()
        assert "@Configuration" in code

    def test_enable_caching_import(self, gen):
        code = gen._gen_cache_config()
        assert "EnableCaching" in code

    def test_mentions_redis(self, gen):
        code = gen._gen_cache_config()
        assert "Redis" in code or "redis" in code.lower()

    def test_mentions_cacheable(self, gen):
        code = gen._gen_cache_config()
        assert "@Cacheable" in code


# ═══════════════════════════════════════════════════════════════════
#  Security Config (OAuth)
# ═══════════════════════════════════════════════════════════════════

class TestSecurityConfig:
    def test_has_bean_annotation(self, gen):
        code = gen._gen_security_config()
        assert "@Bean" in code

    def test_security_filter_chain(self, gen):
        code = gen._gen_security_config()
        assert "SecurityFilterChain" in code

    def test_csrf_disabled(self, gen):
        code = gen._gen_security_config()
        assert "csrf" in code
        assert "disable" in code

    def test_actuator_permitted(self, gen):
        code = gen._gen_security_config()
        assert "/actuator/**" in code
        assert "permitAll" in code

    def test_oauth2_resource_server(self, gen):
        code = gen._gen_security_config()
        assert "oauth2ResourceServer" in code

    def test_jwt_configured(self, gen):
        code = gen._gen_security_config()
        assert "jwt" in code


# ═══════════════════════════════════════════════════════════════════
#  Async Config
# ═══════════════════════════════════════════════════════════════════

class TestAsyncConfig:
    def test_has_bean_annotation(self, gen):
        code = gen._gen_async_config()
        assert "@Bean" in code

    def test_thread_pool_task_executor(self, gen):
        code = gen._gen_async_config()
        assert "ThreadPoolTaskExecutor" in code

    def test_core_pool_size_set(self, gen):
        code = gen._gen_async_config()
        assert "setCorePoolSize" in code

    def test_max_pool_size_set(self, gen):
        code = gen._gen_async_config()
        assert "setMaxPoolSize" in code

    def test_enable_async_import(self, gen):
        code = gen._gen_async_config()
        assert "EnableAsync" in code


# ═══════════════════════════════════════════════════════════════════
#  SFTP Config
# ═══════════════════════════════════════════════════════════════════

class TestSftpConfig:
    def test_has_bean_annotations(self, gen):
        code = gen._gen_sftp_config()
        assert code.count("@Bean") >= 2  # session factory + template

    def test_sftp_session_factory(self, gen):
        code = gen._gen_sftp_config()
        assert "DefaultSftpSessionFactory" in code

    def test_sftp_template(self, gen):
        code = gen._gen_sftp_config()
        assert "SftpRemoteFileTemplate" in code

    def test_configurable_properties(self, gen):
        code = gen._gen_sftp_config()
        assert "${sftp.host}" in code
        assert "${sftp.port" in code
        assert "${sftp.username}" in code


# ═══════════════════════════════════════════════════════════════════
#  AWS S3 Config
# ═══════════════════════════════════════════════════════════════════

class TestS3Config:
    def test_has_bean_annotation(self, gen):
        code = gen._gen_s3_config()
        assert "@Bean" in code

    def test_s3_client(self, gen):
        code = gen._gen_s3_config()
        assert "S3Client" in code

    def test_region_configured(self, gen):
        code = gen._gen_s3_config()
        assert "Region.US_EAST_1" in code


# ═══════════════════════════════════════════════════════════════════
#  AWS SQS Config
# ═══════════════════════════════════════════════════════════════════

class TestSqsConfig:
    def test_has_bean_annotation(self, gen):
        code = gen._gen_sqs_config()
        assert "@Bean" in code

    def test_sqs_client(self, gen):
        code = gen._gen_sqs_config()
        assert "SqsClient" in code


# ═══════════════════════════════════════════════════════════════════
#  Web Service Config
# ═══════════════════════════════════════════════════════════════════

class TestWebServiceConfig:
    def test_has_bean_annotation(self, gen):
        code = gen._gen_ws_config()
        assert "@Bean" in code

    def test_web_service_template(self, gen):
        code = gen._gen_ws_config()
        assert "WebServiceTemplate" in code


# ═══════════════════════════════════════════════════════════════════
#  CORS Config
# ═══════════════════════════════════════════════════════════════════

class TestCorsConfig:
    def test_has_bean_annotation(self, gen):
        code = gen._gen_cors_config()
        assert "@Bean" in code

    def test_cors_configurer(self, gen):
        code = gen._gen_cors_config()
        assert "WebMvcConfigurer" in code

    def test_add_cors_mappings(self, gen):
        code = gen._gen_cors_config()
        assert "addCorsMappings" in code

    def test_all_origins_allowed(self, gen):
        code = gen._gen_cors_config()
        assert 'allowedOrigins("*")' in code

    def test_all_http_methods_allowed(self, gen):
        code = gen._gen_cors_config()
        for method in ("GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"):
            assert f'"{method}"' in code

    def test_all_headers_allowed(self, gen):
        code = gen._gen_cors_config()
        assert 'allowedHeaders("*")' in code

    def test_all_paths_mapped(self, gen):
        code = gen._gen_cors_config()
        assert 'addMapping("/**")' in code


# ═══════════════════════════════════════════════════════════════════
#  Conditional Config Generation (full pipeline)
# ═══════════════════════════════════════════════════════════════════

class TestConditionalConfigGeneration:
    def _generate_files(self, mule_xml):
        from backend.migrator.parser import MuleSoftParser
        parser = MuleSoftParser()
        parsed = parser.parse(mule_xml)
        dw = DataWeaveConverter()
        mapper = ConnectorMapper()
        converter = FlowConverter(dw, mapper)
        spring_files = converter.convert(parsed, {})
        connector_info = mapper.map_connectors(parsed)
        gen = SpringBootGenerator("test-app", "com.example")
        return gen.generate(spring_files, connector_info, parsed)

    def test_cors_config_always_generated(self):
        xml = '<?xml version="1.0"?><mule xmlns="http://www.mulesoft.org/schema/mule/core"></mule>'
        files = self._generate_files(xml)
        assert any("CorsConfig.java" in k for k in files)

    def test_jms_config_generated_when_jms_present(self):
        xml = """\
<?xml version="1.0" encoding="UTF-8"?>
<mule xmlns="http://www.mulesoft.org/schema/mule/core"
      xmlns:jms="http://www.mulesoft.org/schema/mule/jms">
    <jms:config name="JMS_Config"/>
    <flow name="jms-flow">
        <jms:listener config-ref="JMS_Config" destination="q"/>
        <logger message="msg"/>
    </flow>
</mule>"""
        files = self._generate_files(xml)
        assert any("JmsConfig.java" in k for k in files)

    def test_kafka_config_generated_when_kafka_present(self):
        xml = """\
<?xml version="1.0" encoding="UTF-8"?>
<mule xmlns="http://www.mulesoft.org/schema/mule/core"
      xmlns:kafka="http://www.mulesoft.org/schema/mule/kafka">
    <kafka:consumer-config name="Kafka_Config"/>
    <flow name="k-flow">
        <kafka:consumer config-ref="Kafka_Config" topic="t"/>
    </flow>
</mule>"""
        files = self._generate_files(xml)
        assert any("KafkaConfig.java" in k for k in files)

    def test_security_config_generated_when_oauth(self):
        xml = """\
<?xml version="1.0" encoding="UTF-8"?>
<mule xmlns="http://www.mulesoft.org/schema/mule/core"
      xmlns:secure-properties="http://www.mulesoft.org/schema/mule/secure-properties">
    <secure-properties:config name="sp" file="secure.yaml" key="k">
        <secure-properties:encrypt algorithm="AES" mode="CBC"/>
    </secure-properties:config>
</mule>"""
        files = self._generate_files(xml)
        assert any("SecurityConfig.java" in k for k in files)

    def test_no_jms_config_when_jms_absent(self):
        xml = """\
<?xml version="1.0" encoding="UTF-8"?>
<mule xmlns="http://www.mulesoft.org/schema/mule/core"
      xmlns:http="http://www.mulesoft.org/schema/mule/http">
    <http:listener-config name="HTTP" host="0.0.0.0" port="8081"/>
    <flow name="f">
        <http:listener config-ref="HTTP" path="/api" method="GET"/>
    </flow>
</mule>"""
        files = self._generate_files(xml)
        assert not any("JmsConfig.java" in k for k in files)


# Need these imports for the conditional tests
from backend.migrator.connector_mapper import ConnectorMapper
from backend.migrator.dataweave_converter import DataWeaveConverter
from backend.migrator.flow_converter import FlowConverter
