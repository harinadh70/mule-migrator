"""
Seed the RAG knowledge base with MuleSoft -> Spring Boot migration patterns.

Indexes detailed migration pattern documents into PostgreSQL pgvector
via Azure OpenAI text-embedding-3-large embeddings.

Usage:
    python seed_knowledge.py

Required env vars:
    PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD
    AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT  (default: text-embedding-3-large)

Can also be invoked programmatically via ``seed_all()``.
"""

from __future__ import annotations

import asyncio
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("seed_knowledge")

KNOWLEDGE_DOCUMENTS: list[dict] = [
    # ==================================================================
    #  1. HTTP Patterns (15 docs)
    # ==================================================================
    {
        "title": "HTTP Listener GET Endpoint",
        "category": "mulesoft",
        "content": """MuleSoft HTTP Listener GET -> Spring Boot @GetMapping

MuleSoft XML:
```xml
<http:listener-config name="HTTP_Listener" host="0.0.0.0" port="8081"/>
<flow name="getCustomersFlow">
    <http:listener config-ref="HTTP_Listener" path="/api/customers" method="GET"/>
    <logger level="INFO" message="Fetching all customers"/>
    <db:select config-ref="Database_Config">
        <db:sql>SELECT * FROM customers</db:sql>
    </db:select>
    <ee:transform>
        <ee:set-payload><![CDATA[%dw 2.0
output application/json
---
payload]]></ee:set-payload>
    </ee:transform>
</flow>
```

Spring Boot Java:
```java
@RestController
@RequestMapping("/api")
@Slf4j
public class CustomerController {

    private final CustomerService customerService;

    public CustomerController(CustomerService customerService) {
        this.customerService = customerService;
    }

    @GetMapping("/customers")
    public ResponseEntity<List<CustomerDTO>> getAllCustomers() {
        log.info("Fetching all customers");
        List<CustomerDTO> customers = customerService.findAll();
        return ResponseEntity.ok(customers);
    }
}
```

Key mapping rules:
- Each MuleSoft <http:listener> with method="GET" becomes a @GetMapping method.
- The listener path attribute maps directly to the @GetMapping value.
- Logger components become SLF4J log statements.
- Database select followed by transform becomes a service call returning DTOs.
- Use @RequestMapping at class level for common path prefix like /api.""",
    },
    {
        "title": "HTTP Listener POST Endpoint",
        "category": "mulesoft",
        "content": """MuleSoft HTTP Listener POST -> Spring Boot @PostMapping

MuleSoft XML:
```xml
<flow name="createCustomerFlow">
    <http:listener config-ref="HTTP_Listener" path="/api/customers" method="POST"/>
    <logger level="INFO" message="Creating customer: #[payload]"/>
    <ee:transform>
        <ee:set-variable variableName="customerData"><![CDATA[%dw 2.0
output application/java
---
payload]]></ee:set-variable>
    </ee:transform>
    <db:insert config-ref="Database_Config">
        <db:sql>INSERT INTO customers (name, email) VALUES (:name, :email)</db:sql>
        <db:input-parameters><![CDATA[#[{name: vars.customerData.name, email: vars.customerData.email}]]]></db:input-parameters>
    </db:insert>
    <set-payload value='{"status": "created"}'/>
</flow>
```

Spring Boot Java:
```java
@PostMapping("/customers")
public ResponseEntity<CustomerDTO> createCustomer(@Valid @RequestBody CreateCustomerRequest request) {
    log.info("Creating customer: {}", request.getName());
    CustomerDTO created = customerService.create(request);
    URI location = ServletUriComponentsBuilder.fromCurrentRequest()
        .path("/{id}").buildAndExpand(created.getId()).toUri();
    return ResponseEntity.created(location).body(created);
}
```

Key mapping rules:
- POST listener becomes @PostMapping with @RequestBody for the JSON payload.
- MuleSoft payload auto-parsing maps to Spring's automatic Jackson deserialization.
- Use @Valid for request validation; define constraints on the request DTO.
- Return 201 Created with a Location header pointing to the new resource.
- DB insert logic moves into the service layer, not the controller.""",
    },
    {
        "title": "HTTP Listener PUT Endpoint",
        "category": "mulesoft",
        "content": """MuleSoft HTTP Listener PUT -> Spring Boot @PutMapping

MuleSoft XML:
```xml
<flow name="updateCustomerFlow">
    <http:listener config-ref="HTTP_Listener" path="/api/customers/{id}" method="PUT"/>
    <set-variable variableName="customerId" value="#[attributes.uriParams.id]"/>
    <logger level="INFO" message="Updating customer #[vars.customerId]"/>
    <db:update config-ref="Database_Config">
        <db:sql>UPDATE customers SET name = :name, email = :email WHERE id = :id</db:sql>
        <db:input-parameters><![CDATA[#[{id: vars.customerId, name: payload.name, email: payload.email}]]]></db:input-parameters>
    </db:update>
</flow>
```

Spring Boot Java:
```java
@PutMapping("/customers/{id}")
public ResponseEntity<CustomerDTO> updateCustomer(
        @PathVariable Long id,
        @Valid @RequestBody UpdateCustomerRequest request) {
    log.info("Updating customer {}", id);
    CustomerDTO updated = customerService.update(id, request);
    return ResponseEntity.ok(updated);
}
```

Key mapping rules:
- PUT listener with path params becomes @PutMapping with @PathVariable.
- MuleSoft attributes.uriParams.id maps to @PathVariable Long id.
- Combine path variable and request body for update operations.
- Service layer handles the find-then-update logic and throws NotFoundException if missing.
- Return 200 OK with the updated resource.""",
    },
    {
        "title": "HTTP Listener DELETE Endpoint",
        "category": "mulesoft",
        "content": """MuleSoft HTTP Listener DELETE -> Spring Boot @DeleteMapping

MuleSoft XML:
```xml
<flow name="deleteCustomerFlow">
    <http:listener config-ref="HTTP_Listener" path="/api/customers/{id}" method="DELETE"/>
    <set-variable variableName="customerId" value="#[attributes.uriParams.id]"/>
    <logger level="INFO" message="Deleting customer #[vars.customerId]"/>
    <db:delete config-ref="Database_Config">
        <db:sql>DELETE FROM customers WHERE id = :id</db:sql>
        <db:input-parameters><![CDATA[#[{id: vars.customerId}]]]></db:input-parameters>
    </db:delete>
    <set-payload value='{"status": "deleted"}'/>
</flow>
```

Spring Boot Java:
```java
@DeleteMapping("/customers/{id}")
public ResponseEntity<Void> deleteCustomer(@PathVariable Long id) {
    log.info("Deleting customer {}", id);
    customerService.delete(id);
    return ResponseEntity.noContent().build();
}
```

Key mapping rules:
- DELETE listener becomes @DeleteMapping with @PathVariable.
- Return 204 No Content for successful deletions (REST best practice).
- Service layer should verify existence before deleting and throw NotFoundException if not found.
- MuleSoft db:delete maps to JPA repository.deleteById() or a custom delete query.""",
    },
    {
        "title": "HTTP Listener PATCH Endpoint",
        "category": "mulesoft",
        "content": """MuleSoft HTTP Listener PATCH -> Spring Boot @PatchMapping

MuleSoft XML:
```xml
<flow name="patchCustomerFlow">
    <http:listener config-ref="HTTP_Listener" path="/api/customers/{id}" method="PATCH"/>
    <set-variable variableName="customerId" value="#[attributes.uriParams.id]"/>
    <logger level="INFO" message="Patching customer #[vars.customerId]"/>
    <db:update config-ref="Database_Config">
        <db:sql>UPDATE customers SET email = :email WHERE id = :id</db:sql>
        <db:input-parameters><![CDATA[#[{id: vars.customerId, email: payload.email}]]]></db:input-parameters>
    </db:update>
</flow>
```

Spring Boot Java:
```java
@PatchMapping("/customers/{id}")
public ResponseEntity<CustomerDTO> patchCustomer(
        @PathVariable Long id,
        @RequestBody Map<String, Object> updates) {
    log.info("Patching customer {}", id);
    CustomerDTO patched = customerService.patch(id, updates);
    return ResponseEntity.ok(patched);
}
```

Key mapping rules:
- PATCH listener becomes @PatchMapping for partial updates.
- Accept a Map or a dedicated PatchRequest DTO for flexible partial updates.
- Service layer selectively applies only the provided fields.
- Use BeanUtils or manual null-checking to merge partial updates onto the existing entity.
- Return 200 OK with the patched resource.""",
    },
    {
        "title": "HTTP Listener with Path Parameters",
        "category": "mulesoft",
        "content": """MuleSoft HTTP Listener Path Params -> Spring Boot @PathVariable

MuleSoft XML:
```xml
<flow name="getOrderItemFlow">
    <http:listener config-ref="HTTP_Listener" path="/api/orders/{orderId}/items/{itemId}" method="GET"/>
    <set-variable variableName="orderId" value="#[attributes.uriParams.orderId]"/>
    <set-variable variableName="itemId" value="#[attributes.uriParams.itemId]"/>
    <logger level="INFO" message="Fetching item #[vars.itemId] from order #[vars.orderId]"/>
    <db:select config-ref="Database_Config">
        <db:sql>SELECT * FROM order_items WHERE order_id = :orderId AND id = :itemId</db:sql>
        <db:input-parameters><![CDATA[#[{orderId: vars.orderId, itemId: vars.itemId}]]]></db:input-parameters>
    </db:select>
</flow>
```

Spring Boot Java:
```java
@GetMapping("/orders/{orderId}/items/{itemId}")
public ResponseEntity<OrderItemDTO> getOrderItem(
        @PathVariable Long orderId,
        @PathVariable Long itemId) {
    log.info("Fetching item {} from order {}", itemId, orderId);
    OrderItemDTO item = orderItemService.findByOrderAndId(orderId, itemId);
    return ResponseEntity.ok(item);
}
```

Key mapping rules:
- MuleSoft {param} in path maps to Spring Boot {param} with @PathVariable.
- attributes.uriParams.paramName maps to @PathVariable Type paramName.
- Multiple path parameters are supported; name them to match the path template.
- Spring auto-converts string path variables to the declared type (Long, UUID, etc.).""",
    },
    {
        "title": "HTTP Listener with Query Parameters",
        "category": "mulesoft",
        "content": """MuleSoft HTTP Listener Query Params -> Spring Boot @RequestParam

MuleSoft XML:
```xml
<flow name="searchCustomersFlow">
    <http:listener config-ref="HTTP_Listener" path="/api/customers" method="GET"/>
    <set-variable variableName="nameFilter" value="#[attributes.queryParams.name]"/>
    <set-variable variableName="page" value="#[attributes.queryParams.page default 0]"/>
    <set-variable variableName="size" value="#[attributes.queryParams.size default 20]"/>
    <db:select config-ref="Database_Config">
        <db:sql>SELECT * FROM customers WHERE name LIKE :name LIMIT :size OFFSET :offset</db:sql>
        <db:input-parameters><![CDATA[#[{name: '%' ++ vars.nameFilter ++ '%', size: vars.size, offset: vars.page * vars.size}]]]></db:input-parameters>
    </db:select>
</flow>
```

Spring Boot Java:
```java
@GetMapping("/customers")
public ResponseEntity<Page<CustomerDTO>> searchCustomers(
        @RequestParam(required = false) String name,
        @RequestParam(defaultValue = "0") int page,
        @RequestParam(defaultValue = "20") int size) {
    log.info("Searching customers with name={}, page={}, size={}", name, page, size);
    Page<CustomerDTO> results = customerService.search(name, PageRequest.of(page, size));
    return ResponseEntity.ok(results);
}
```

Key mapping rules:
- MuleSoft attributes.queryParams.paramName maps to @RequestParam.
- Default values use defaultValue attribute instead of DataWeave default operator.
- Optional parameters use required = false.
- Pagination parameters (page, size) map naturally to Spring Data Pageable.""",
    },
    {
        "title": "HTTP Listener with Headers",
        "category": "mulesoft",
        "content": """MuleSoft HTTP Listener Headers -> Spring Boot @RequestHeader

MuleSoft XML:
```xml
<flow name="processOrderFlow">
    <http:listener config-ref="HTTP_Listener" path="/api/orders" method="POST"/>
    <set-variable variableName="correlationId" value="#[attributes.headers.'X-Correlation-ID']"/>
    <set-variable variableName="clientId" value="#[attributes.headers.'X-Client-ID']"/>
    <logger level="INFO" message="Processing order, correlationId=#[vars.correlationId]"/>
</flow>
```

Spring Boot Java:
```java
@PostMapping("/orders")
public ResponseEntity<OrderDTO> processOrder(
        @RequestHeader(value = "X-Correlation-ID", required = false) String correlationId,
        @RequestHeader("X-Client-ID") String clientId,
        @Valid @RequestBody CreateOrderRequest request) {
    log.info("Processing order, correlationId={}", correlationId);
    OrderDTO order = orderService.create(request, clientId, correlationId);
    return ResponseEntity.status(HttpStatus.CREATED).body(order);
}
```

Key mapping rules:
- MuleSoft attributes.headers.'Header-Name' maps to @RequestHeader("Header-Name").
- Optional headers use required = false.
- You can also use HttpServletRequest.getHeader() for dynamic header access.
- For reading all headers, inject HttpHeaders parameter.""",
    },
    {
        "title": "HTTP Listener with Request Body Validation",
        "category": "mulesoft",
        "content": """MuleSoft Validation Module -> Spring Boot @Valid + Bean Validation

MuleSoft XML:
```xml
<flow name="createProductFlow">
    <http:listener config-ref="HTTP_Listener" path="/api/products" method="POST"/>
    <validation:is-not-null value="#[payload.name]" message="Product name is required"/>
    <validation:validate-size value="#[payload.name]" min="1" max="255" message="Name must be 1-255 chars"/>
    <validation:is-not-null value="#[payload.price]" message="Price is required"/>
    <validation:is-true expression="#[payload.price > 0]" message="Price must be positive"/>
    <db:insert config-ref="Database_Config">
        <db:sql>INSERT INTO products (name, price, description) VALUES (:name, :price, :desc)</db:sql>
        <db:input-parameters><![CDATA[#[{name: payload.name, price: payload.price, desc: payload.description}]]]></db:input-parameters>
    </db:insert>
</flow>
```

Spring Boot Java:
```java
public class CreateProductRequest {
    @NotNull(message = "Product name is required")
    @Size(min = 1, max = 255, message = "Name must be 1-255 chars")
    private String name;

    @NotNull(message = "Price is required")
    @Positive(message = "Price must be positive")
    private BigDecimal price;

    private String description;
}

@PostMapping("/products")
public ResponseEntity<ProductDTO> createProduct(@Valid @RequestBody CreateProductRequest request) {
    ProductDTO product = productService.create(request);
    return ResponseEntity.status(HttpStatus.CREATED).body(product);
}
```

Key mapping rules:
- MuleSoft validation:is-not-null maps to @NotNull.
- validation:validate-size maps to @Size.
- validation:is-true with expression maps to custom @Constraint or @Positive/@Negative.
- All validations are declared on the DTO class, not inline in the controller.
- @Valid triggers automatic validation; errors produce 400 Bad Request.""",
    },
    {
        "title": "HTTP Request Outbound GET",
        "category": "mulesoft",
        "content": """MuleSoft HTTP Request GET -> Spring Boot WebClient / RestTemplate

MuleSoft XML:
```xml
<http:request-config name="External_API" host="api.example.com" port="443" protocol="HTTPS"/>
<flow name="fetchExternalDataFlow">
    <http:listener config-ref="HTTP_Listener" path="/api/external-data" method="GET"/>
    <http:request config-ref="External_API" path="/v1/data/{id}" method="GET">
        <http:uri-params><![CDATA[#[{id: attributes.queryParams.id}]]]></http:uri-params>
        <http:headers><![CDATA[#[{'Accept': 'application/json'}]]]></http:headers>
    </http:request>
</flow>
```

Spring Boot Java (WebClient):
```java
@Service
@Slf4j
public class ExternalApiClient {

    private final WebClient webClient;

    public ExternalApiClient(WebClient.Builder builder) {
        this.webClient = builder.baseUrl("https://api.example.com").build();
    }

    public Mono<DataDTO> fetchData(String id) {
        return webClient.get()
            .uri("/v1/data/{id}", id)
            .accept(MediaType.APPLICATION_JSON)
            .retrieve()
            .bodyToMono(DataDTO.class);
    }
}
```

Key mapping rules:
- MuleSoft http:request-config becomes a WebClient bean with baseUrl.
- http:request GET becomes webClient.get().uri().retrieve().
- URI parameters use the same {param} template syntax.
- Headers are set via .header() or .accept() methods.
- Prefer WebClient over RestTemplate for new projects (RestTemplate is in maintenance mode).""",
    },
    {
        "title": "HTTP Request Outbound POST",
        "category": "mulesoft",
        "content": """MuleSoft HTTP Request POST -> Spring Boot WebClient POST

MuleSoft XML:
```xml
<flow name="sendOrderFlow">
    <http:request config-ref="External_API" path="/v1/orders" method="POST">
        <http:body><![CDATA[#[output application/json --- {orderId: vars.orderId, items: vars.items}]]]></http:body>
        <http:headers><![CDATA[#[{'Content-Type': 'application/json', 'Authorization': 'Bearer ' ++ vars.token}]]]></http:headers>
    </http:request>
</flow>
```

Spring Boot Java:
```java
public OrderResponse sendOrder(OrderRequest request, String token) {
    return webClient.post()
        .uri("/v1/orders")
        .contentType(MediaType.APPLICATION_JSON)
        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
        .bodyValue(request)
        .retrieve()
        .bodyToMono(OrderResponse.class)
        .block();
}
```

Key mapping rules:
- MuleSoft http:request POST with body becomes webClient.post().bodyValue().
- DataWeave output in http:body maps to a Java DTO serialized via Jackson.
- Headers set in http:headers map to .header() calls.
- Use .block() only in non-reactive code; prefer returning Mono in reactive pipelines.""",
    },
    {
        "title": "HTTP Request with Basic and Bearer Authentication",
        "category": "mulesoft",
        "content": """MuleSoft HTTP Request Auth -> Spring Boot WebClient with Auth

MuleSoft XML (Basic Auth):
```xml
<http:request-config name="Secured_API">
    <http:request-connection host="secure-api.example.com" port="443" protocol="HTTPS">
        <http:authentication>
            <http:basic-authentication username="${api.username}" password="${api.password}"/>
        </http:authentication>
    </http:request-connection>
</http:request-config>
```

MuleSoft XML (Bearer Token):
```xml
<http:request config-ref="Secured_API" path="/v1/secure-data" method="GET">
    <http:headers><![CDATA[#[{'Authorization': 'Bearer ' ++ vars.accessToken}]]]></http:headers>
</http:request>
```

Spring Boot Java:
```java
@Configuration
public class WebClientConfig {

    @Bean("basicAuthClient")
    public WebClient basicAuthClient(
            @Value("${api.username}") String username,
            @Value("${api.password}") String password) {
        return WebClient.builder()
            .baseUrl("https://secure-api.example.com")
            .defaultHeaders(headers -> headers.setBasicAuth(username, password))
            .build();
    }

    @Bean("bearerAuthClient")
    public WebClient bearerAuthClient() {
        return WebClient.builder()
            .baseUrl("https://secure-api.example.com")
            .filter(ExchangeFilterFunctions.bearerAuthentication(() -> tokenService.getToken()))
            .build();
    }
}
```

Key mapping rules:
- MuleSoft basic-authentication maps to headers.setBasicAuth() or a default header.
- Bearer token maps to an Authorization header or an ExchangeFilterFunction.
- Store credentials in application.yml using environment variable references.
- For OAuth2 client credentials flow, use Spring Security OAuth2 Client.""",
    },
    {
        "title": "HTTP Listener Error Responses",
        "category": "mulesoft",
        "content": """MuleSoft HTTP Error Responses -> Spring Boot ResponseEntity + @ControllerAdvice

MuleSoft XML:
```xml
<flow name="getCustomerFlow">
    <http:listener config-ref="HTTP_Listener" path="/api/customers/{id}" method="GET"/>
    <db:select config-ref="Database_Config">
        <db:sql>SELECT * FROM customers WHERE id = :id</db:sql>
        <db:input-parameters><![CDATA[#[{id: attributes.uriParams.id}]]]></db:input-parameters>
    </db:select>
    <choice>
        <when expression="#[sizeOf(payload) == 0]">
            <set-payload value='{"error": "Customer not found"}'/>
            <set-variable variableName="httpStatus" value="404"/>
        </when>
    </choice>
    <error-handler>
        <on-error-propagate type="DB:CONNECTIVITY">
            <set-payload value='{"error": "Service unavailable"}'/>
            <set-variable variableName="httpStatus" value="503"/>
        </on-error-propagate>
    </error-handler>
</flow>
```

Spring Boot Java:
```java
@ControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(ResourceNotFoundException.class)
    public ResponseEntity<ErrorResponse> handleNotFound(ResourceNotFoundException ex) {
        ErrorResponse error = new ErrorResponse(404, ex.getMessage());
        return ResponseEntity.status(HttpStatus.NOT_FOUND).body(error);
    }

    @ExceptionHandler(DataAccessException.class)
    public ResponseEntity<ErrorResponse> handleDbError(DataAccessException ex) {
        ErrorResponse error = new ErrorResponse(503, "Service unavailable");
        return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE).body(error);
    }
}
```

Key mapping rules:
- MuleSoft choice with error payload and httpStatus variable maps to throwing specific exceptions.
- on-error-propagate maps to @ExceptionHandler methods in @ControllerAdvice.
- Use custom exception classes (ResourceNotFoundException, etc.) for each HTTP error code.
- Return structured ErrorResponse DTOs for consistent API error formatting.""",
    },
    {
        "title": "HTTP Listener CORS Configuration",
        "category": "mulesoft",
        "content": """MuleSoft CORS Interceptor -> Spring Boot CORS Configuration

MuleSoft XML:
```xml
<http:listener-config name="HTTP_Listener">
    <http:listener-connection host="0.0.0.0" port="8081"/>
    <http:listener-interceptors>
        <http:cors-interceptor>
            <http:origins>
                <http:origin url="https://app.example.com" accessControlMaxAge="86400">
                    <http:allowed-methods>
                        <http:method methodName="GET"/>
                        <http:method methodName="POST"/>
                        <http:method methodName="PUT"/>
                        <http:method methodName="DELETE"/>
                    </http:allowed-methods>
                    <http:allowed-headers>
                        <http:header headerName="Content-Type"/>
                        <http:header headerName="Authorization"/>
                    </http:allowed-headers>
                </http:origin>
            </http:origins>
        </http:cors-interceptor>
    </http:listener-interceptors>
</http:listener-config>
```

Spring Boot Java:
```java
@Configuration
public class CorsConfig implements WebMvcConfigurer {

    @Override
    public void addCorsMappings(CorsRegistry registry) {
        registry.addMapping("/api/**")
            .allowedOrigins("https://app.example.com")
            .allowedMethods("GET", "POST", "PUT", "DELETE")
            .allowedHeaders("Content-Type", "Authorization")
            .maxAge(86400);
    }
}
```

Key mapping rules:
- MuleSoft cors-interceptor maps to WebMvcConfigurer.addCorsMappings().
- Allowed origins, methods, headers, and maxAge all have direct equivalents.
- For per-endpoint CORS, use @CrossOrigin annotation on controller methods.
- In Spring Security setups, also configure CORS in the security filter chain.""",
    },
    {
        "title": "HTTP Listener TLS/SSL Configuration",
        "category": "mulesoft",
        "content": """MuleSoft TLS Context -> Spring Boot SSL Configuration

MuleSoft XML:
```xml
<tls:context name="TLS_Context">
    <tls:key-store type="jks" path="keystore.jks" keyPassword="${tls.keyPassword}" password="${tls.storePassword}"/>
    <tls:trust-store type="jks" path="truststore.jks" password="${tls.trustPassword}"/>
</tls:context>
<http:listener-config name="HTTPS_Listener">
    <http:listener-connection host="0.0.0.0" port="8443" protocol="HTTPS" tlsContext="TLS_Context"/>
</http:listener-config>
```

Spring Boot application.yml:
```yaml
server:
  port: 8443
  ssl:
    enabled: true
    key-store: classpath:keystore.jks
    key-store-password: ${TLS_STORE_PASSWORD}
    key-password: ${TLS_KEY_PASSWORD}
    key-store-type: JKS
    trust-store: classpath:truststore.jks
    trust-store-password: ${TLS_TRUST_PASSWORD}
    trust-store-type: JKS
```

Spring Boot Java (for mutual TLS):
```java
@Configuration
public class SslConfig {

    @Bean
    public WebClient mutualTlsWebClient() throws Exception {
        SslContext sslContext = SslContextBuilder.forClient()
            .keyManager(new File("client.crt"), new File("client.key"))
            .trustManager(new File("ca.crt"))
            .build();
        HttpClient httpClient = HttpClient.create()
            .secure(spec -> spec.sslContext(sslContext));
        return WebClient.builder()
            .clientConnector(new ReactorClientHttpConnector(httpClient))
            .build();
    }
}
```

Key mapping rules:
- MuleSoft tls:context maps to server.ssl properties in application.yml.
- Key store and trust store paths and passwords have direct equivalents.
- For outbound mutual TLS, configure SSLContext on the WebClient/HttpClient.
- Use environment variables for all passwords; never hard-code them.""",
    },
    {
        "title": "HTTP Request Timeout and Retry",
        "category": "mulesoft",
        "content": """MuleSoft HTTP Request Timeout/Retry -> Spring Boot WebClient Timeout + Resilience4j Retry

MuleSoft XML:
```xml
<http:request-config name="External_API" responseTimeout="5000">
    <http:request-connection host="api.example.com" port="443" protocol="HTTPS"/>
</http:request-config>
<flow name="callWithRetryFlow">
    <until-successful maxRetries="3" millisBetweenRetries="2000">
        <http:request config-ref="External_API" path="/v1/data" method="GET"/>
    </until-successful>
</flow>
```

Spring Boot Java:
```java
@Configuration
public class WebClientConfig {

    @Bean
    public WebClient externalApiClient() {
        HttpClient httpClient = HttpClient.create()
            .responseTimeout(Duration.ofSeconds(5))
            .option(ChannelOption.CONNECT_TIMEOUT_MILLIS, 5000);
        return WebClient.builder()
            .baseUrl("https://api.example.com")
            .clientConnector(new ReactorClientHttpConnector(httpClient))
            .build();
    }
}

@Service
@Slf4j
public class ExternalApiService {

    @Retry(name = "externalApi", fallbackMethod = "fallback")
    public DataDTO fetchData() {
        return webClient.get().uri("/v1/data")
            .retrieve().bodyToMono(DataDTO.class).block();
    }

    private DataDTO fallback(Exception ex) {
        log.error("All retries failed for external API", ex);
        throw new ServiceUnavailableException("External API unavailable");
    }
}
```

application.yml:
```yaml
resilience4j:
  retry:
    instances:
      externalApi:
        maxAttempts: 3
        waitDuration: 2s
        retryExceptions:
          - java.io.IOException
          - org.springframework.web.reactive.function.client.WebClientResponseException
```

Key mapping rules:
- MuleSoft responseTimeout maps to httpClient.responseTimeout().
- until-successful maps to Resilience4j @Retry annotation.
- maxRetries and millisBetweenRetries map to retry configuration properties.
- Define a fallback method for when all retries are exhausted.""",
    },
    {
        "title": "HTTP Request with Query Parameters",
        "category": "mulesoft",
        "content": """MuleSoft HTTP Request Query Params -> Spring Boot WebClient Query Params

MuleSoft XML:
```xml
<flow name="searchExternalFlow">
    <http:request config-ref="External_API" path="/v1/search" method="GET">
        <http:query-params><![CDATA[#[{
            q: vars.searchTerm,
            page: vars.page,
            limit: vars.limit,
            sort: 'name:asc'
        }]]]></http:query-params>
    </http:request>
</flow>
```

Spring Boot Java:
```java
public SearchResult search(String searchTerm, int page, int limit) {
    return webClient.get()
        .uri(uriBuilder -> uriBuilder
            .path("/v1/search")
            .queryParam("q", searchTerm)
            .queryParam("page", page)
            .queryParam("limit", limit)
            .queryParam("sort", "name:asc")
            .build())
        .retrieve()
        .bodyToMono(SearchResult.class)
        .block();
}
```

Key mapping rules:
- MuleSoft http:query-params map becomes .queryParam() calls in UriBuilder.
- Use UriBuilder lambda for building query strings.
- Special characters are automatically URL-encoded by Spring's UriBuilder.
- For dynamic query params, use a Map<String, String> and iterate over entries.""",
    },
    {
        "title": "HTTP Listener Multipart Form Data",
        "category": "mulesoft",
        "content": """MuleSoft Multipart Handling -> Spring Boot MultipartFile

MuleSoft XML:
```xml
<flow name="uploadFileFlow">
    <http:listener config-ref="HTTP_Listener" path="/api/upload" method="POST">
        <http:response statusCode="201"/>
    </http:listener>
    <set-variable variableName="filePart" value="#[payload.parts.file]"/>
    <set-variable variableName="fileName" value="#[vars.filePart.headers.'Content-Disposition'.filename]"/>
    <file:write config-ref="File_Config" path="#['/uploads/' ++ vars.fileName]">
        <file:content>#[vars.filePart.content]</file:content>
    </file:write>
</flow>
```

Spring Boot Java:
```java
@PostMapping(value = "/upload", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
public ResponseEntity<UploadResponse> uploadFile(
        @RequestParam("file") MultipartFile file) {
    log.info("Uploading file: {}, size: {}", file.getOriginalFilename(), file.getSize());
    String savedPath = fileStorageService.store(file);
    UploadResponse response = new UploadResponse(savedPath, file.getOriginalFilename());
    return ResponseEntity.status(HttpStatus.CREATED).body(response);
}
```

Key mapping rules:
- MuleSoft payload.parts.file maps to @RequestParam("file") MultipartFile.
- File metadata (name, content type, size) available via MultipartFile methods.
- Configure max file size in application.yml under spring.servlet.multipart.
- Move file storage logic to a dedicated FileStorageService.""",
    },
    {
        "title": "HTTP Request Proxy Configuration",
        "category": "mulesoft",
        "content": """MuleSoft HTTP Proxy -> Spring Boot WebClient Proxy

MuleSoft XML:
```xml
<http:request-config name="Proxied_API">
    <http:request-connection host="api.example.com" port="443" protocol="HTTPS">
        <http:proxy-config>
            <http:proxy host="${proxy.host}" port="${proxy.port}"
                        username="${proxy.username}" password="${proxy.password}"/>
        </http:proxy-config>
    </http:request-connection>
</http:request-config>
```

Spring Boot Java:
```java
@Bean
public WebClient proxiedWebClient(
        @Value("${proxy.host}") String proxyHost,
        @Value("${proxy.port}") int proxyPort) {
    HttpClient httpClient = HttpClient.create()
        .proxy(proxy -> proxy
            .type(ProxyProvider.Proxy.HTTP)
            .host(proxyHost)
            .port(proxyPort));
    return WebClient.builder()
        .baseUrl("https://api.example.com")
        .clientConnector(new ReactorClientHttpConnector(httpClient))
        .build();
}
```

Key mapping rules:
- MuleSoft http:proxy-config maps to HttpClient.proxy() configuration.
- Proxy host, port, username, password all have direct equivalents.
- For authenticated proxies, add .username() and .password() to the proxy spec.
- Configure proxy via application.yml for environment-specific settings.""",
    },
    {
        "title": "Content Type Negotiation JSON and XML",
        "category": "mulesoft",
        "content": """MuleSoft Content Type Handling -> Spring Boot Content Negotiation

MuleSoft XML:
```xml
<flow name="getDataFlow">
    <http:listener config-ref="HTTP_Listener" path="/api/data" method="GET"/>
    <choice>
        <when expression="#[attributes.headers.'Accept' == 'application/xml']">
            <ee:transform>
                <ee:set-payload><![CDATA[%dw 2.0
output application/xml
---
{data: payload}]]></ee:set-payload>
            </ee:transform>
        </when>
        <otherwise>
            <ee:transform>
                <ee:set-payload><![CDATA[%dw 2.0
output application/json
---
payload]]></ee:set-payload>
            </ee:transform>
        </otherwise>
    </choice>
</flow>
```

Spring Boot Java:
```java
@GetMapping(value = "/data", produces = {MediaType.APPLICATION_JSON_VALUE, MediaType.APPLICATION_XML_VALUE})
public ResponseEntity<DataDTO> getData(
        @RequestHeader(value = "Accept", defaultValue = "application/json") String accept) {
    DataDTO data = dataService.getData();
    return ResponseEntity.ok(data);
}
```

application.yml:
```yaml
spring:
  mvc:
    contentnegotiation:
      favor-parameter: false
      favor-path-extension: false
```

pom.xml dependency for XML support:
```xml
<dependency>
    <groupId>com.fasterxml.jackson.dataformat</groupId>
    <artifactId>jackson-dataformat-xml</artifactId>
</dependency>
```

Key mapping rules:
- MuleSoft choice on Accept header is automatic in Spring Boot with content negotiation.
- Add produces attribute to specify supported media types.
- Add jackson-dataformat-xml dependency for XML serialization.
- Spring automatically picks the format based on the Accept header.""",
    },
    # ==================================================================
    #  2. Database Patterns (15 docs)
    # ==================================================================
    {
        "title": "DB Select to JPA findAll",
        "category": "mulesoft",
        "content": """MuleSoft db:select -> Spring Boot JPA Repository findAll

MuleSoft XML:
```xml
<db:config name="Database_Config">
    <db:generic-connection url="jdbc:postgresql://localhost:5432/mydb"
        user="${db.user}" password="${db.password}"/>
</db:config>
<flow name="getAllProductsFlow">
    <http:listener config-ref="HTTP_Listener" path="/api/products" method="GET"/>
    <db:select config-ref="Database_Config">
        <db:sql>SELECT * FROM products</db:sql>
    </db:select>
    <ee:transform>
        <ee:set-payload><![CDATA[%dw 2.0
output application/json
---
payload]]></ee:set-payload>
    </ee:transform>
</flow>
```

Spring Boot Java:
```java
@Entity
@Table(name = "products")
public class Product {
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    private String name;
    private BigDecimal price;
    private String description;
}

public interface ProductRepository extends JpaRepository<Product, Long> {
}

@Service
public class ProductService {
    private final ProductRepository repository;
    public ProductService(ProductRepository repository) { this.repository = repository; }

    public List<ProductDTO> findAll() {
        return repository.findAll().stream()
            .map(this::toDTO)
            .collect(Collectors.toList());
    }
}
```

Key mapping rules:
- db:select with simple SELECT * maps to JpaRepository.findAll().
- Database config maps to spring.datasource properties in application.yml.
- Each table becomes a JPA @Entity class; repository extends JpaRepository.
- Transform to JSON is handled automatically by Jackson serialization.""",
    },
    {
        "title": "DB Select with WHERE to JPA findBy",
        "category": "mulesoft",
        "content": """MuleSoft db:select WHERE -> Spring Boot JPA Derived Query / @Query

MuleSoft XML:
```xml
<flow name="getProductsByCategory">
    <http:listener config-ref="HTTP_Listener" path="/api/products" method="GET"/>
    <db:select config-ref="Database_Config">
        <db:sql>SELECT * FROM products WHERE category = :category AND price BETWEEN :minPrice AND :maxPrice</db:sql>
        <db:input-parameters><![CDATA[#[{
            category: attributes.queryParams.category,
            minPrice: attributes.queryParams.minPrice,
            maxPrice: attributes.queryParams.maxPrice
        }]]]></db:input-parameters>
    </db:select>
</flow>
```

Spring Boot Java:
```java
public interface ProductRepository extends JpaRepository<Product, Long> {
    // Derived query method
    List<Product> findByCategoryAndPriceBetween(String category, BigDecimal minPrice, BigDecimal maxPrice);

    // Or explicit JPQL
    @Query("SELECT p FROM Product p WHERE p.category = :category AND p.price BETWEEN :minPrice AND :maxPrice")
    List<Product> searchProducts(@Param("category") String category,
                                  @Param("minPrice") BigDecimal minPrice,
                                  @Param("maxPrice") BigDecimal maxPrice);
}
```

Key mapping rules:
- db:select with WHERE maps to JPA derived queries or @Query JPQL.
- MuleSoft :param placeholders map to @Param annotations in Spring Data.
- Simple conditions like WHERE x = :val map to findByX(val) derived methods.
- Complex conditions (BETWEEN, LIKE, IN) use @Query with JPQL.""",
    },
    {
        "title": "DB Select with JOIN to JPA Query",
        "category": "mulesoft",
        "content": """MuleSoft db:select JOIN -> Spring Boot @Query JPQL Join

MuleSoft XML:
```xml
<flow name="getOrdersWithItems">
    <db:select config-ref="Database_Config">
        <db:sql>SELECT o.id, o.order_date, o.status, i.product_name, i.quantity, i.price
            FROM orders o
            JOIN order_items i ON o.id = i.order_id
            WHERE o.customer_id = :customerId</db:sql>
        <db:input-parameters><![CDATA[#[{customerId: vars.customerId}]]]></db:input-parameters>
    </db:select>
</flow>
```

Spring Boot Java:
```java
@Entity
public class Order {
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    private LocalDate orderDate;
    private String status;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "customer_id")
    private Customer customer;

    @OneToMany(mappedBy = "order", cascade = CascadeType.ALL)
    private List<OrderItem> items;
}

public interface OrderRepository extends JpaRepository<Order, Long> {
    @Query("SELECT o FROM Order o JOIN FETCH o.items WHERE o.customer.id = :customerId")
    List<Order> findByCustomerIdWithItems(@Param("customerId") Long customerId);
}
```

Key mapping rules:
- SQL JOINs map to JPA entity relationships (@ManyToOne, @OneToMany).
- Use JOIN FETCH in JPQL to eagerly load associations and avoid N+1 queries.
- The join condition (ON o.id = i.order_id) is expressed via @JoinColumn.
- For complex projections, consider using DTO projections with constructor expressions.""",
    },
    {
        "title": "DB Insert to JPA save",
        "category": "mulesoft",
        "content": """MuleSoft db:insert -> Spring Boot JPA save / JdbcTemplate.update

MuleSoft XML:
```xml
<flow name="createProductFlow">
    <db:insert config-ref="Database_Config" autoGenerateKeys="true">
        <db:sql>INSERT INTO products (name, price, category, description)
                VALUES (:name, :price, :category, :description)</db:sql>
        <db:input-parameters><![CDATA[#[{
            name: payload.name,
            price: payload.price,
            category: payload.category,
            description: payload.description
        }]]]></db:input-parameters>
    </db:insert>
</flow>
```

Spring Boot Java (JPA):
```java
@Service
@Transactional
public class ProductService {
    private final ProductRepository repository;

    public ProductDTO create(CreateProductRequest request) {
        Product product = new Product();
        product.setName(request.getName());
        product.setPrice(request.getPrice());
        product.setCategory(request.getCategory());
        product.setDescription(request.getDescription());
        Product saved = repository.save(product);
        return toDTO(saved);
    }
}
```

Spring Boot Java (JdbcTemplate alternative):
```java
@Repository
public class ProductJdbcRepository {
    private final JdbcTemplate jdbc;

    public Long insert(Product product) {
        KeyHolder keyHolder = new GeneratedKeyHolder();
        jdbc.update(connection -> {
            PreparedStatement ps = connection.prepareStatement(
                "INSERT INTO products (name, price, category, description) VALUES (?, ?, ?, ?)",
                Statement.RETURN_GENERATED_KEYS);
            ps.setString(1, product.getName());
            ps.setBigDecimal(2, product.getPrice());
            ps.setString(3, product.getCategory());
            ps.setString(4, product.getDescription());
            return ps;
        }, keyHolder);
        return keyHolder.getKey().longValue();
    }
}
```

Key mapping rules:
- db:insert maps to JPA repository.save() for new entities.
- autoGenerateKeys=true maps to @GeneratedValue on the ID field.
- For JdbcTemplate, use KeyHolder to retrieve auto-generated keys.
- Prefer JPA save() for simple inserts; use JdbcTemplate for complex SQL.""",
    },
    {
        "title": "DB Update to JPA save",
        "category": "mulesoft",
        "content": """MuleSoft db:update -> Spring Boot JPA save / @Modifying @Query

MuleSoft XML:
```xml
<flow name="updateProductFlow">
    <db:update config-ref="Database_Config">
        <db:sql>UPDATE products SET name = :name, price = :price WHERE id = :id</db:sql>
        <db:input-parameters><![CDATA[#[{id: vars.productId, name: payload.name, price: payload.price}]]]></db:input-parameters>
    </db:update>
</flow>
```

Spring Boot Java:
```java
@Service
@Transactional
public class ProductService {
    public ProductDTO update(Long id, UpdateProductRequest request) {
        Product product = repository.findById(id)
            .orElseThrow(() -> new ResourceNotFoundException("Product", id));
        product.setName(request.getName());
        product.setPrice(request.getPrice());
        Product updated = repository.save(product);
        return toDTO(updated);
    }
}

// Or using @Modifying for bulk updates:
public interface ProductRepository extends JpaRepository<Product, Long> {
    @Modifying
    @Query("UPDATE Product p SET p.price = :price WHERE p.category = :category")
    int updatePriceByCategory(@Param("price") BigDecimal price, @Param("category") String category);
}
```

Key mapping rules:
- db:update for single row maps to find-then-save pattern in JPA.
- db:update for bulk updates maps to @Modifying @Query in repository.
- Always fetch the entity first to ensure it exists before updating.
- Use @Transactional to ensure atomic read-then-write operations.""",
    },
    {
        "title": "DB Delete to JPA deleteById",
        "category": "mulesoft",
        "content": """MuleSoft db:delete -> Spring Boot JPA deleteById

MuleSoft XML:
```xml
<flow name="deleteProductFlow">
    <db:delete config-ref="Database_Config">
        <db:sql>DELETE FROM products WHERE id = :id</db:sql>
        <db:input-parameters><![CDATA[#[{id: vars.productId}]]]></db:input-parameters>
    </db:delete>
    <choice>
        <when expression="#[payload.affectedRows == 0]">
            <raise-error type="APP:NOT_FOUND" description="Product not found"/>
        </when>
    </choice>
</flow>
```

Spring Boot Java:
```java
@Service
@Transactional
public class ProductService {
    public void delete(Long id) {
        if (!repository.existsById(id)) {
            throw new ResourceNotFoundException("Product", id);
        }
        repository.deleteById(id);
    }
}
```

Key mapping rules:
- db:delete maps to JPA repository.deleteById().
- Checking affectedRows == 0 maps to existsById() check before delete.
- raise-error APP:NOT_FOUND maps to throwing ResourceNotFoundException.
- For soft deletes, use @SQLDelete and @Where annotations on the entity.""",
    },
    {
        "title": "DB Bulk Insert to JPA saveAll",
        "category": "mulesoft",
        "content": """MuleSoft db:bulk-insert -> Spring Boot JPA saveAll / Batch Insert

MuleSoft XML:
```xml
<flow name="bulkInsertProducts">
    <db:bulk-insert config-ref="Database_Config">
        <db:sql>INSERT INTO products (name, price, category) VALUES (:name, :price, :category)</db:sql>
        <db:bulk-input-parameters><![CDATA[#[payload map {name: $.name, price: $.price, category: $.category}]]]></db:bulk-input-parameters>
    </db:bulk-insert>
</flow>
```

Spring Boot Java:
```java
@Service
@Transactional
public class ProductService {
    public List<ProductDTO> bulkCreate(List<CreateProductRequest> requests) {
        List<Product> products = requests.stream()
            .map(this::toEntity)
            .collect(Collectors.toList());
        List<Product> saved = repository.saveAll(products);
        return saved.stream().map(this::toDTO).collect(Collectors.toList());
    }
}
```

application.yml for batch optimization:
```yaml
spring:
  jpa:
    properties:
      hibernate:
        jdbc:
          batch_size: 50
        order_inserts: true
        order_updates: true
```

Key mapping rules:
- db:bulk-insert maps to JPA saveAll() with batch configuration.
- Configure hibernate.jdbc.batch_size for efficient batch inserts.
- Enable order_inserts and order_updates for optimal batching.
- For very large datasets, consider JdbcTemplate.batchUpdate() for better performance.""",
    },
    {
        "title": "DB Stored Procedure to Spring @Procedure",
        "category": "mulesoft",
        "content": """MuleSoft db:stored-procedure -> Spring Boot @Procedure / SimpleJdbcCall

MuleSoft XML:
```xml
<flow name="callStoredProcFlow">
    <db:stored-procedure config-ref="Database_Config">
        <db:sql>CALL calculate_monthly_totals(:year, :month)</db:sql>
        <db:input-parameters><![CDATA[#[{year: vars.year, month: vars.month}]]]></db:input-parameters>
        <db:output-parameters>
            <db:output-parameter key="total" type="DOUBLE"/>
            <db:output-parameter key="count" type="INTEGER"/>
        </db:output-parameters>
    </db:stored-procedure>
</flow>
```

Spring Boot Java (JPA @Procedure):
```java
public interface ReportRepository extends JpaRepository<Report, Long> {
    @Procedure(name = "calculate_monthly_totals")
    Map<String, Object> calculateMonthlyTotals(@Param("year") int year, @Param("month") int month);
}
```

Spring Boot Java (SimpleJdbcCall):
```java
@Repository
public class ReportJdbcRepository {
    private final SimpleJdbcCall jdbcCall;

    public ReportJdbcRepository(DataSource dataSource) {
        this.jdbcCall = new SimpleJdbcCall(dataSource)
            .withProcedureName("calculate_monthly_totals")
            .declareParameters(
                new SqlParameter("year", Types.INTEGER),
                new SqlParameter("month", Types.INTEGER),
                new SqlOutParameter("total", Types.DOUBLE),
                new SqlOutParameter("count", Types.INTEGER));
    }

    public MonthlyTotal calculateTotals(int year, int month) {
        Map<String, Object> result = jdbcCall.execute(
            new MapSqlParameterSource()
                .addValue("year", year)
                .addValue("month", month));
        return new MonthlyTotal((Double) result.get("total"), (Integer) result.get("count"));
    }
}
```

Key mapping rules:
- db:stored-procedure maps to @Procedure annotation or SimpleJdbcCall.
- Input parameters map to @Param annotations or MapSqlParameterSource.
- Output parameters map to declared SqlOutParameter in SimpleJdbcCall.
- Use SimpleJdbcCall for procedures with complex output parameters.""",
    },
    {
        "title": "DB Select with Pagination",
        "category": "mulesoft",
        "content": """MuleSoft db:select with LIMIT/OFFSET -> Spring Boot Pageable

MuleSoft XML:
```xml
<flow name="getPagedProducts">
    <http:listener config-ref="HTTP_Listener" path="/api/products" method="GET"/>
    <db:select config-ref="Database_Config">
        <db:sql>SELECT * FROM products ORDER BY name LIMIT :limit OFFSET :offset</db:sql>
        <db:input-parameters><![CDATA[#[{
            limit: attributes.queryParams.size default 20,
            offset: (attributes.queryParams.page default 0) * (attributes.queryParams.size default 20)
        }]]]></db:input-parameters>
    </db:select>
</flow>
```

Spring Boot Java:
```java
@GetMapping("/products")
public ResponseEntity<Page<ProductDTO>> getProducts(
        @RequestParam(defaultValue = "0") int page,
        @RequestParam(defaultValue = "20") int size,
        @RequestParam(defaultValue = "name") String sortBy) {
    Pageable pageable = PageRequest.of(page, size, Sort.by(sortBy));
    Page<ProductDTO> products = productService.findAll(pageable);
    return ResponseEntity.ok(products);
}

// Service:
public Page<ProductDTO> findAll(Pageable pageable) {
    return repository.findAll(pageable).map(this::toDTO);
}
```

Key mapping rules:
- MuleSoft LIMIT/OFFSET maps to Spring Data Pageable and PageRequest.
- Query params page and size map to PageRequest.of(page, size).
- Sorting maps to Sort.by() passed into PageRequest.
- Spring Data automatically generates the paginated SQL.
- The Page response includes totalElements, totalPages, and content.""",
    },
    {
        "title": "Database Connection Pooling with HikariCP",
        "category": "mulesoft",
        "content": """MuleSoft DB Connection Pool -> Spring Boot HikariCP Configuration

MuleSoft XML:
```xml
<db:config name="Database_Config">
    <db:generic-connection url="jdbc:postgresql://${db.host}:${db.port}/${db.name}"
        user="${db.user}" password="${db.password}">
        <db:pooling-profile maxPoolSize="20" minPoolSize="5" acquireIncrement="2"
            maxWait="30" maxWaitUnit="SECONDS"/>
    </db:generic-connection>
</db:config>
```

Spring Boot application.yml:
```yaml
spring:
  datasource:
    url: jdbc:postgresql://${DB_HOST:localhost}:${DB_PORT:5432}/${DB_NAME:mydb}
    username: ${DB_USER:app}
    password: ${DB_PASSWORD:}
    hikari:
      maximum-pool-size: 20
      minimum-idle: 5
      idle-timeout: 300000
      connection-timeout: 30000
      max-lifetime: 1800000
      pool-name: MyAppPool
      leak-detection-threshold: 60000
```

Spring Boot Java (programmatic config):
```java
@Configuration
public class DataSourceConfig {
    @Bean
    @ConfigurationProperties(prefix = "spring.datasource.hikari")
    public HikariDataSource dataSource() {
        return DataSourceBuilder.create().type(HikariDataSource.class).build();
    }
}
```

Key mapping rules:
- MuleSoft pooling-profile maxPoolSize maps to hikari.maximum-pool-size.
- minPoolSize maps to hikari.minimum-idle.
- maxWait maps to hikari.connection-timeout (in milliseconds).
- HikariCP is the default pool in Spring Boot; no extra dependency needed.
- Add leak-detection-threshold to catch connection leaks during development.""",
    },
    {
        "title": "Transaction Management",
        "category": "mulesoft",
        "content": """MuleSoft Transaction Scope -> Spring Boot @Transactional

MuleSoft XML:
```xml
<flow name="transferFundsFlow">
    <try transactionalAction="ALWAYS_BEGIN">
        <db:update config-ref="Database_Config">
            <db:sql>UPDATE accounts SET balance = balance - :amount WHERE id = :fromId</db:sql>
            <db:input-parameters><![CDATA[#[{fromId: payload.fromAccountId, amount: payload.amount}]]]></db:input-parameters>
        </db:update>
        <db:update config-ref="Database_Config">
            <db:sql>UPDATE accounts SET balance = balance + :amount WHERE id = :toId</db:sql>
            <db:input-parameters><![CDATA[#[{toId: payload.toAccountId, amount: payload.amount}]]]></db:input-parameters>
        </db:update>
        <error-handler>
            <on-error-propagate>
                <logger level="ERROR" message="Transfer failed, rolling back"/>
            </on-error-propagate>
        </error-handler>
    </try>
</flow>
```

Spring Boot Java:
```java
@Service
public class TransferService {
    private final AccountRepository accountRepository;

    @Transactional(rollbackFor = Exception.class)
    public TransferResult transfer(TransferRequest request) {
        Account from = accountRepository.findById(request.getFromAccountId())
            .orElseThrow(() -> new ResourceNotFoundException("Account", request.getFromAccountId()));
        Account to = accountRepository.findById(request.getToAccountId())
            .orElseThrow(() -> new ResourceNotFoundException("Account", request.getToAccountId()));

        if (from.getBalance().compareTo(request.getAmount()) < 0) {
            throw new InsufficientFundsException("Insufficient balance");
        }

        from.setBalance(from.getBalance().subtract(request.getAmount()));
        to.setBalance(to.getBalance().add(request.getAmount()));

        accountRepository.save(from);
        accountRepository.save(to);
        return new TransferResult("SUCCESS", request.getAmount());
    }
}
```

Key mapping rules:
- MuleSoft try with transactionalAction="ALWAYS_BEGIN" maps to @Transactional.
- on-error-propagate in transaction scope maps to automatic rollback on exception.
- Use rollbackFor = Exception.class to rollback on checked exceptions too.
- Spring manages transaction begin, commit, and rollback automatically.""",
    },
    {
        "title": "Multiple Datasources Configuration",
        "category": "mulesoft",
        "content": """MuleSoft Multiple DB Configs -> Spring Boot Multiple DataSources

MuleSoft XML:
```xml
<db:config name="Primary_DB">
    <db:generic-connection url="jdbc:postgresql://primary-host:5432/maindb" user="${primary.user}" password="${primary.password}"/>
</db:config>
<db:config name="Analytics_DB">
    <db:generic-connection url="jdbc:postgresql://analytics-host:5432/analyticsdb" user="${analytics.user}" password="${analytics.password}"/>
</db:config>
```

Spring Boot Java:
```java
@Configuration
public class DataSourceConfig {

    @Primary
    @Bean
    @ConfigurationProperties("spring.datasource.primary")
    public DataSource primaryDataSource() {
        return DataSourceBuilder.create().build();
    }

    @Bean
    @ConfigurationProperties("spring.datasource.analytics")
    public DataSource analyticsDataSource() {
        return DataSourceBuilder.create().build();
    }

    @Primary
    @Bean
    public LocalContainerEntityManagerFactoryBean primaryEntityManager(
            @Qualifier("primaryDataSource") DataSource ds) {
        LocalContainerEntityManagerFactoryBean em = new LocalContainerEntityManagerFactoryBean();
        em.setDataSource(ds);
        em.setPackagesToScan("com.example.domain.primary");
        em.setJpaVendorAdapter(new HibernateJpaVendorAdapter());
        return em;
    }

    @Bean
    public LocalContainerEntityManagerFactoryBean analyticsEntityManager(
            @Qualifier("analyticsDataSource") DataSource ds) {
        LocalContainerEntityManagerFactoryBean em = new LocalContainerEntityManagerFactoryBean();
        em.setDataSource(ds);
        em.setPackagesToScan("com.example.domain.analytics");
        em.setJpaVendorAdapter(new HibernateJpaVendorAdapter());
        return em;
    }
}
```

Key mapping rules:
- Each MuleSoft db:config maps to a separate DataSource @Bean.
- Use @Primary to mark the default datasource.
- Each datasource gets its own EntityManagerFactory and TransactionManager.
- Entities for each database are in separate packages for scanning.""",
    },
    {
        "title": "Database Migration with Flyway",
        "category": "mulesoft",
        "content": """MuleSoft Manual Schema -> Spring Boot Flyway Database Migration

MuleSoft does not have built-in database migration. Schemas are managed manually or externally.

Spring Boot with Flyway:

pom.xml:
```xml
<dependency>
    <groupId>org.flywaydb</groupId>
    <artifactId>flyway-core</artifactId>
</dependency>
```

application.yml:
```yaml
spring:
  flyway:
    enabled: true
    locations: classpath:db/migration
    baseline-on-migrate: true
```

Migration file (src/main/resources/db/migration/V1__create_products.sql):
```sql
CREATE TABLE products (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    category VARCHAR(100),
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_products_category ON products(category);
```

V2__add_status_column.sql:
```sql
ALTER TABLE products ADD COLUMN status VARCHAR(20) DEFAULT 'ACTIVE';
```

Key mapping rules:
- When migrating MuleSoft apps, create Flyway migrations to match existing schema.
- Use V{version}__{description}.sql naming convention for migrations.
- Set ddl-auto to validate (not update/create) in production.
- Flyway tracks applied migrations in a flyway_schema_history table.
- Each migration runs once and is never modified after deployment.""",
    },
    {
        "title": "Optimistic Locking with @Version",
        "category": "mulesoft",
        "content": """MuleSoft Manual Locking -> Spring Boot JPA @Version Optimistic Lock

MuleSoft XML (manual optimistic lock):
```xml
<flow name="updateWithLock">
    <db:select config-ref="Database_Config">
        <db:sql>SELECT * FROM products WHERE id = :id</db:sql>
        <db:input-parameters><![CDATA[#[{id: vars.productId}]]]></db:input-parameters>
    </db:select>
    <set-variable variableName="currentVersion" value="#[payload[0].version]"/>
    <db:update config-ref="Database_Config">
        <db:sql>UPDATE products SET name = :name, version = :newVersion WHERE id = :id AND version = :oldVersion</db:sql>
        <db:input-parameters><![CDATA[#[{id: vars.productId, name: payload.name, newVersion: vars.currentVersion + 1, oldVersion: vars.currentVersion}]]]></db:input-parameters>
    </db:update>
</flow>
```

Spring Boot Java:
```java
@Entity
public class Product {
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    private String name;
    private BigDecimal price;

    @Version
    private Long version;
}

@Service
@Transactional
public class ProductService {
    public ProductDTO update(Long id, UpdateProductRequest request) {
        Product product = repository.findById(id)
            .orElseThrow(() -> new ResourceNotFoundException("Product", id));
        product.setName(request.getName());
        try {
            Product saved = repository.save(product);
            return toDTO(saved);
        } catch (OptimisticLockingFailureException e) {
            throw new ConflictException("Product was modified by another user");
        }
    }
}
```

Key mapping rules:
- MuleSoft manual version checking maps to JPA @Version annotation.
- JPA automatically checks and increments the version field on save.
- OptimisticLockingFailureException is thrown on version mismatch.
- Map this to HTTP 409 Conflict in @ControllerAdvice.""",
    },
    {
        "title": "Audit Fields with @EntityListeners",
        "category": "mulesoft",
        "content": """MuleSoft Manual Timestamps -> Spring Boot JPA Auditing

MuleSoft XML:
```xml
<flow name="createWithTimestamp">
    <set-variable variableName="now" value="#[now()]"/>
    <db:insert config-ref="Database_Config">
        <db:sql>INSERT INTO products (name, created_at, updated_at) VALUES (:name, :createdAt, :updatedAt)</db:sql>
        <db:input-parameters><![CDATA[#[{name: payload.name, createdAt: vars.now, updatedAt: vars.now}]]]></db:input-parameters>
    </db:insert>
</flow>
```

Spring Boot Java:
```java
@MappedSuperclass
@EntityListeners(AuditingEntityListener.class)
public abstract class BaseEntity {
    @CreatedDate
    @Column(updatable = false)
    private LocalDateTime createdAt;

    @LastModifiedDate
    private LocalDateTime updatedAt;

    @CreatedBy
    @Column(updatable = false)
    private String createdBy;

    @LastModifiedBy
    private String updatedBy;
}

@Entity
public class Product extends BaseEntity {
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    private String name;
}

@Configuration
@EnableJpaAuditing
public class JpaAuditConfig {
    @Bean
    public AuditorAware<String> auditorProvider() {
        return () -> Optional.ofNullable(SecurityContextHolder.getContext()
            .getAuthentication()).map(Authentication::getName);
    }
}
```

Key mapping rules:
- MuleSoft manual now() timestamps map to @CreatedDate and @LastModifiedDate.
- Create a BaseEntity with audit fields that all entities extend.
- Enable JPA auditing with @EnableJpaAuditing.
- AuditorAware provides the current user for @CreatedBy/@LastModifiedBy.
- Audit fields are managed automatically by Spring Data.""",
    },
    # ==================================================================
    #  3. DataWeave Patterns (25 docs)
    # ==================================================================
    {
        "title": "DataWeave map to Java Stream.map",
        "category": "dataweave",
        "content": """DataWeave map -> Java Stream.map()

MuleSoft DataWeave:
```xml
<ee:transform>
    <ee:set-payload><![CDATA[%dw 2.0
output application/json
---
payload map {
    fullName: $.firstName ++ " " ++ $.lastName,
    email: $.email,
    age: $.age
}]]></ee:set-payload>
</ee:transform>
```

Spring Boot Java:
```java
List<CustomerDTO> result = customers.stream()
    .map(c -> new CustomerDTO(
        c.getFirstName() + " " + c.getLastName(),
        c.getEmail(),
        c.getAge()))
    .collect(Collectors.toList());
```

Key mapping rules:
- DataWeave map iterates and transforms each element, equivalent to Stream.map().
- $ references the current element, mapping to the lambda parameter.
- $.fieldName maps to getter methods on the Java object.
- String concatenation (++) maps to Java + operator or String.concat().
- Collect results with Collectors.toList().""",
    },
    {
        "title": "DataWeave filter to Java Stream.filter",
        "category": "dataweave",
        "content": """DataWeave filter -> Java Stream.filter()

MuleSoft DataWeave:
```xml
<ee:transform>
    <ee:set-payload><![CDATA[%dw 2.0
output application/json
---
payload filter ($.status == "ACTIVE" and $.age >= 18)]]></ee:set-payload>
</ee:transform>
```

Spring Boot Java:
```java
List<Customer> active = customers.stream()
    .filter(c -> "ACTIVE".equals(c.getStatus()) && c.getAge() >= 18)
    .collect(Collectors.toList());
```

Key mapping rules:
- DataWeave filter with predicate maps directly to Stream.filter().
- DataWeave and maps to Java &&; or maps to ||.
- DataWeave == comparison maps to .equals() for objects, == for primitives.
- Chain multiple filter() calls or combine predicates with && for readability.""",
    },
    {
        "title": "DataWeave reduce to Java Stream.reduce",
        "category": "dataweave",
        "content": """DataWeave reduce -> Java Stream.reduce()

MuleSoft DataWeave:
```xml
<ee:transform>
    <ee:set-payload><![CDATA[%dw 2.0
output application/json
---
{
    totalAmount: payload.items reduce ((item, acc = 0) -> acc + item.price * item.quantity),
    itemCount: sizeOf(payload.items)
}]]></ee:set-payload>
</ee:transform>
```

Spring Boot Java:
```java
BigDecimal totalAmount = order.getItems().stream()
    .map(item -> item.getPrice().multiply(BigDecimal.valueOf(item.getQuantity())))
    .reduce(BigDecimal.ZERO, BigDecimal::add);

OrderSummary summary = new OrderSummary(totalAmount, order.getItems().size());
```

Key mapping rules:
- DataWeave reduce with accumulator maps to Stream.reduce(identity, accumulator).
- The initial value (acc = 0) maps to the identity parameter.
- For summing numbers, use BigDecimal for precision in financial calculations.
- sizeOf() maps to .size() on collections.""",
    },
    {
        "title": "DataWeave groupBy to Collectors.groupingBy",
        "category": "dataweave",
        "content": """DataWeave groupBy -> Java Collectors.groupingBy()

MuleSoft DataWeave:
```xml
<ee:transform>
    <ee:set-payload><![CDATA[%dw 2.0
output application/json
---
payload groupBy $.category]]></ee:set-payload>
</ee:transform>
```

Spring Boot Java:
```java
Map<String, List<Product>> grouped = products.stream()
    .collect(Collectors.groupingBy(Product::getCategory));
```

Key mapping rules:
- DataWeave groupBy $.field maps directly to Collectors.groupingBy(getter).
- The result is a Map<KeyType, List<ElementType>>.
- For downstream collectors (counting, summing), use groupingBy with a second argument.
- DataWeave returns an Object with keys; Java returns a Map.""",
    },
    {
        "title": "DataWeave orderBy to Stream.sorted",
        "category": "dataweave",
        "content": """DataWeave orderBy -> Java Stream.sorted()

MuleSoft DataWeave:
```xml
<ee:transform>
    <ee:set-payload><![CDATA[%dw 2.0
output application/json
---
payload orderBy $.name
// or descending: payload orderBy -$.price]]></ee:set-payload>
</ee:transform>
```

Spring Boot Java:
```java
// Ascending
List<Product> sorted = products.stream()
    .sorted(Comparator.comparing(Product::getName))
    .collect(Collectors.toList());

// Descending
List<Product> sortedDesc = products.stream()
    .sorted(Comparator.comparing(Product::getPrice).reversed())
    .collect(Collectors.toList());

// Multiple fields
List<Product> multiSorted = products.stream()
    .sorted(Comparator.comparing(Product::getCategory)
        .thenComparing(Product::getName))
    .collect(Collectors.toList());
```

Key mapping rules:
- DataWeave orderBy $.field maps to Stream.sorted(Comparator.comparing()).
- Descending order (-$.field) maps to .reversed() on the comparator.
- Multiple sort fields use .thenComparing() chaining.""",
    },
    {
        "title": "DataWeave distinctBy to Stream.distinct",
        "category": "dataweave",
        "content": """DataWeave distinctBy -> Java Stream.distinct / custom

MuleSoft DataWeave:
```xml
<ee:transform>
    <ee:set-payload><![CDATA[%dw 2.0
output application/json
---
payload distinctBy $.email]]></ee:set-payload>
</ee:transform>
```

Spring Boot Java:
```java
// Simple distinct (uses equals/hashCode)
List<String> uniqueEmails = customers.stream()
    .map(Customer::getEmail)
    .distinct()
    .collect(Collectors.toList());

// Distinct by field (keeping full objects)
List<Customer> uniqueByEmail = customers.stream()
    .collect(Collectors.collectingAndThen(
        Collectors.toMap(Customer::getEmail, Function.identity(), (a, b) -> a),
        map -> new ArrayList<>(map.values())));
```

Key mapping rules:
- DataWeave distinctBy $.field needs a custom approach in Java if keeping full objects.
- For simple value dedup, use Stream.distinct().
- For object dedup by a field, use Collectors.toMap with merge function.
- TreeSet with custom comparator is another option for ordered dedup.""",
    },
    {
        "title": "DataWeave flatMap to Stream.flatMap",
        "category": "dataweave",
        "content": """DataWeave flatMap -> Java Stream.flatMap()

MuleSoft DataWeave:
```xml
<ee:transform>
    <ee:set-payload><![CDATA[%dw 2.0
output application/json
---
payload flatMap $.items]]></ee:set-payload>
</ee:transform>
```

Spring Boot Java:
```java
List<OrderItem> allItems = orders.stream()
    .flatMap(order -> order.getItems().stream())
    .collect(Collectors.toList());
```

Key mapping rules:
- DataWeave flatMap flattens nested arrays, same as Stream.flatMap().
- $.items accesses the nested collection; .stream() converts it for flatMapping.
- flatMap is essential for one-to-many transformations (orders -> all items).
- Use flatMap when each element expands to zero or more elements.""",
    },
    {
        "title": "DataWeave pluck to Map.entrySet",
        "category": "dataweave",
        "content": """DataWeave pluck -> Java Map.entrySet() transformation

MuleSoft DataWeave:
```xml
<ee:transform>
    <ee:set-payload><![CDATA[%dw 2.0
output application/json
---
payload pluck ((value, key) -> {
    fieldName: key as String,
    fieldValue: value
})]]></ee:set-payload>
</ee:transform>
```

Spring Boot Java:
```java
Map<String, Object> data = getPayloadAsMap();
List<FieldDTO> fields = data.entrySet().stream()
    .map(entry -> new FieldDTO(entry.getKey(), entry.getValue()))
    .collect(Collectors.toList());
```

Key mapping rules:
- DataWeave pluck converts an object to an array of key-value pairs.
- In Java, Map.entrySet() provides the same key-value iteration.
- pluck is used to convert objects to lists; entrySet().stream() does the same.
- The key parameter maps to entry.getKey(), value to entry.getValue().""",
    },
    {
        "title": "DataWeave mapObject to Map transformation",
        "category": "dataweave",
        "content": """DataWeave mapObject -> Java Map transformation

MuleSoft DataWeave:
```xml
<ee:transform>
    <ee:set-payload><![CDATA[%dw 2.0
output application/json
---
payload mapObject ((value, key) -> {
    (upper(key as String)): value
})]]></ee:set-payload>
</ee:transform>
```

Spring Boot Java:
```java
Map<String, Object> original = getPayload();
Map<String, Object> transformed = original.entrySet().stream()
    .collect(Collectors.toMap(
        e -> e.getKey().toUpperCase(),
        Map.Entry::getValue));
```

Key mapping rules:
- DataWeave mapObject transforms keys and/or values of an object.
- Java equivalent uses entrySet().stream() with Collectors.toMap().
- Key transformation (e.g., upper case) maps to key transform in toMap().
- Value transformation applies via the value mapper function.""",
    },
    {
        "title": "DataWeave filterObject to Map filtering",
        "category": "dataweave",
        "content": """DataWeave filterObject -> Java Map filtering

MuleSoft DataWeave:
```xml
<ee:transform>
    <ee:set-payload><![CDATA[%dw 2.0
output application/json
---
payload filterObject ((value, key) -> value != null and value != "")]]></ee:set-payload>
</ee:transform>
```

Spring Boot Java:
```java
Map<String, Object> filtered = original.entrySet().stream()
    .filter(e -> e.getValue() != null && !"".equals(e.getValue()))
    .collect(Collectors.toMap(Map.Entry::getKey, Map.Entry::getValue));
```

Key mapping rules:
- DataWeave filterObject removes key-value pairs based on a predicate.
- Java equivalent filters Map.entrySet() stream and collects back to Map.
- Common use: removing null or empty values before serialization.
- This is useful for PATCH operations where only provided fields should be sent.""",
    },
    {
        "title": "DataWeave sizeOf to Java size/length",
        "category": "dataweave",
        "content": """DataWeave sizeOf -> Java .size() / .length()

MuleSoft DataWeave:
```xml
<ee:transform>
    <ee:set-payload><![CDATA[%dw 2.0
output application/json
---
{
    itemCount: sizeOf(payload.items),
    nameLength: sizeOf(payload.name),
    isEmpty: sizeOf(payload.items) == 0
}]]></ee:set-payload>
</ee:transform>
```

Spring Boot Java:
```java
SummaryDTO summary = new SummaryDTO(
    order.getItems().size(),
    order.getName().length(),
    order.getItems().isEmpty());
```

Key mapping rules:
- DataWeave sizeOf(array) maps to Collection.size().
- DataWeave sizeOf(string) maps to String.length().
- Checking sizeOf(x) == 0 maps to .isEmpty() method.
- Null-safe: use CollectionUtils.isEmpty() or Optional wrapping.""",
    },
    {
        "title": "DataWeave flatten to Stream.flatMap for nested lists",
        "category": "dataweave",
        "content": """DataWeave flatten -> Java Stream.flatMap for nested lists

MuleSoft DataWeave:
```xml
<ee:transform>
    <ee:set-payload><![CDATA[%dw 2.0
output application/json
---
flatten(payload)]]></ee:set-payload>
</ee:transform>
```

Spring Boot Java:
```java
// Flatten a list of lists
List<List<Item>> nested = getNestedItems();
List<Item> flat = nested.stream()
    .flatMap(Collection::stream)
    .collect(Collectors.toList());
```

Key mapping rules:
- DataWeave flatten() takes a nested array and produces a flat array.
- Java equivalent uses Stream.flatMap(Collection::stream).
- Works on List<List<T>> to produce List<T>.
- For deeper nesting, chain multiple flatMap calls.""",
    },
    {
        "title": "DataWeave contains to Java contains",
        "category": "dataweave",
        "content": """DataWeave contains -> Java List.contains / String.contains

MuleSoft DataWeave:
```xml
<ee:transform>
    <ee:set-payload><![CDATA[%dw 2.0
output application/json
---
{
    hasAdmin: payload.roles contains "ADMIN",
    nameContainsJohn: payload.name contains "John",
    statusValid: ["ACTIVE", "PENDING"] contains payload.status
}]]></ee:set-payload>
</ee:transform>
```

Spring Boot Java:
```java
boolean hasAdmin = user.getRoles().contains("ADMIN");
boolean nameContainsJohn = user.getName().contains("John");
boolean statusValid = List.of("ACTIVE", "PENDING").contains(user.getStatus());
```

Key mapping rules:
- DataWeave array contains value maps to List.contains().
- DataWeave string contains substring maps to String.contains().
- DataWeave list contains value maps to List.of(...).contains() or Set.contains().
- Use Set for O(1) lookup when checking membership frequently.""",
    },
    {
        "title": "DataWeave startsWith endsWith to Java String methods",
        "category": "dataweave",
        "content": """DataWeave startsWith/endsWith -> Java String methods

MuleSoft DataWeave:
```xml
<ee:transform>
    <ee:set-payload><![CDATA[%dw 2.0
output application/json
---
payload filter (
    $.email endsWith "@company.com" and
    $.name startsWith "John"
)]]></ee:set-payload>
</ee:transform>
```

Spring Boot Java:
```java
List<Employee> filtered = employees.stream()
    .filter(e -> e.getEmail().endsWith("@company.com")
        && e.getName().startsWith("John"))
    .collect(Collectors.toList());
```

Key mapping rules:
- DataWeave startsWith maps directly to String.startsWith().
- DataWeave endsWith maps directly to String.endsWith().
- Both are case-sensitive; for case-insensitive, convert to lowercase first.
- These methods work identically in DataWeave and Java.""",
    },
    {
        "title": "DataWeave upper lower trim capitalize",
        "category": "dataweave",
        "content": """DataWeave String Functions -> Java String Methods

MuleSoft DataWeave:
```xml
<ee:transform>
    <ee:set-payload><![CDATA[%dw 2.0
output application/json
---
{
    upperName: upper(payload.name),
    lowerEmail: lower(payload.email),
    trimmed: trim(payload.description),
    capitalized: capitalize(payload.title)
}]]></ee:set-payload>
</ee:transform>
```

Spring Boot Java:
```java
import org.apache.commons.text.WordUtils;

String upperName = customer.getName().toUpperCase();
String lowerEmail = customer.getEmail().toLowerCase();
String trimmed = customer.getDescription().trim();
String capitalized = WordUtils.capitalize(customer.getTitle());
```

Key mapping rules:
- DataWeave upper() maps to String.toUpperCase().
- DataWeave lower() maps to String.toLowerCase().
- DataWeave trim() maps to String.trim() or String.strip().
- DataWeave capitalize() maps to Apache Commons Text WordUtils.capitalize().
- For null safety, use StringUtils from Apache Commons Lang.""",
    },
    {
        "title": "DataWeave replace to String.replace",
        "category": "dataweave",
        "content": """DataWeave replace -> Java String.replace / replaceAll

MuleSoft DataWeave:
```xml
<ee:transform>
    <ee:set-payload><![CDATA[%dw 2.0
output application/json
---
{
    cleaned: payload.phone replace /[^0-9]/ with "",
    formatted: payload.name replace " " with "_"
}]]></ee:set-payload>
</ee:transform>
```

Spring Boot Java:
```java
String cleaned = customer.getPhone().replaceAll("[^0-9]", "");
String formatted = customer.getName().replace(" ", "_");
```

Key mapping rules:
- DataWeave replace with regex maps to String.replaceAll() in Java.
- DataWeave replace with literal string maps to String.replace().
- Regex patterns work the same in both DataWeave and Java.
- For complex replacements, use Pattern.compile() for reusable patterns.""",
    },
    {
        "title": "DataWeave splitBy to String.split",
        "category": "dataweave",
        "content": """DataWeave splitBy -> Java String.split()

MuleSoft DataWeave:
```xml
<ee:transform>
    <ee:set-payload><![CDATA[%dw 2.0
output application/json
---
{
    nameParts: payload.fullName splitBy " ",
    tags: payload.tagString splitBy ","
}]]></ee:set-payload>
</ee:transform>
```

Spring Boot Java:
```java
String[] nameParts = customer.getFullName().split(" ");
List<String> tags = Arrays.asList(product.getTagString().split(","));

// With trimming
List<String> cleanTags = Arrays.stream(product.getTagString().split(","))
    .map(String::trim)
    .filter(s -> !s.isEmpty())
    .collect(Collectors.toList());
```

Key mapping rules:
- DataWeave splitBy maps to String.split() in Java.
- split() returns String[]; convert to List with Arrays.asList() if needed.
- Add .map(String::trim) to handle whitespace around delimiters.
- DataWeave splitBy with regex works; Java split() also accepts regex.""",
    },
    {
        "title": "DataWeave joinBy to String.join",
        "category": "dataweave",
        "content": """DataWeave joinBy -> Java String.join()

MuleSoft DataWeave:
```xml
<ee:transform>
    <ee:set-payload><![CDATA[%dw 2.0
output application/json
---
{
    fullName: payload.nameParts joinBy " ",
    csvLine: payload.values joinBy ","
}]]></ee:set-payload>
</ee:transform>
```

Spring Boot Java:
```java
String fullName = String.join(" ", nameParts);
String csvLine = String.join(",", values);

// With stream
String joined = items.stream()
    .map(Item::getName)
    .collect(Collectors.joining(", "));
```

Key mapping rules:
- DataWeave joinBy maps to String.join() for arrays/lists.
- For joining object fields, use Collectors.joining() with Stream.
- String.join() works with both arrays and Iterables.
- Collectors.joining() supports prefix and suffix for wrapping.""",
    },
    {
        "title": "DataWeave match to Java Pattern Matcher",
        "category": "dataweave",
        "content": """DataWeave match/matches -> Java Pattern / Matcher

MuleSoft DataWeave:
```xml
<ee:transform>
    <ee:set-payload><![CDATA[%dw 2.0
output application/json
---
{
    isEmail: payload.email matches /^[\\w.]+@[\\w.]+\\.[a-zA-Z]{2,}$/,
    extracted: (payload.text match /Order-(\\d+)/)[1] default null
}]]></ee:set-payload>
</ee:transform>
```

Spring Boot Java:
```java
import java.util.regex.Matcher;
import java.util.regex.Pattern;

private static final Pattern EMAIL_PATTERN = Pattern.compile("^[\\w.]+@[\\w.]+\\.[a-zA-Z]{2,}$");
private static final Pattern ORDER_PATTERN = Pattern.compile("Order-(\\d+)");

boolean isEmail = EMAIL_PATTERN.matcher(input.getEmail()).matches();

Matcher m = ORDER_PATTERN.matcher(input.getText());
String extracted = m.find() ? m.group(1) : null;
```

Key mapping rules:
- DataWeave matches maps to Pattern.matches() or Matcher.matches().
- DataWeave match with groups maps to Matcher.group(n).
- Compile patterns as static final for reuse and performance.
- DataWeave regex syntax is nearly identical to Java regex.""",
    },
    {
        "title": "DataWeave substringBefore substringAfter",
        "category": "dataweave",
        "content": """DataWeave substringBefore/substringAfter -> Java StringUtils

MuleSoft DataWeave:
```xml
<ee:transform>
    <ee:set-payload><![CDATA[%dw 2.0
import * from dw::core::Strings
output application/json
---
{
    username: substringBefore(payload.email, "@"),
    domain: substringAfter(payload.email, "@"),
    firstName: substringBefore(payload.fullName, " ")
}]]></ee:set-payload>
</ee:transform>
```

Spring Boot Java:
```java
import org.apache.commons.lang3.StringUtils;

String username = StringUtils.substringBefore(email, "@");
String domain = StringUtils.substringAfter(email, "@");
String firstName = StringUtils.substringBefore(fullName, " ");

// Or without Apache Commons:
String username2 = email.substring(0, email.indexOf("@"));
String domain2 = email.substring(email.indexOf("@") + 1);
```

Key mapping rules:
- DataWeave substringBefore maps to StringUtils.substringBefore() (Apache Commons).
- DataWeave substringAfter maps to StringUtils.substringAfter().
- Native Java alternative: String.substring() with indexOf().
- StringUtils handles null safely; native substring throws NullPointerException.""",
    },
    {
        "title": "DataWeave now to LocalDateTime.now",
        "category": "dataweave",
        "content": """DataWeave now() -> Java LocalDateTime.now()

MuleSoft DataWeave:
```xml
<ee:transform>
    <ee:set-payload><![CDATA[%dw 2.0
output application/json
---
{
    timestamp: now(),
    dateOnly: now() as Date,
    formatted: now() as String {format: "yyyy-MM-dd HH:mm:ss"},
    plusDays: now() + |P7D|
}]]></ee:set-payload>
</ee:transform>
```

Spring Boot Java:
```java
import java.time.*;
import java.time.format.DateTimeFormatter;

LocalDateTime timestamp = LocalDateTime.now();
LocalDate dateOnly = LocalDate.now();
String formatted = LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss"));
LocalDateTime plusDays = LocalDateTime.now().plusDays(7);
```

Key mapping rules:
- DataWeave now() maps to LocalDateTime.now() or Instant.now().
- Type coercion (as Date) maps to LocalDate.now().
- Format string maps to DateTimeFormatter.ofPattern().
- Duration addition (+ |P7D|) maps to .plusDays(), .plusHours(), etc.
- Use ZonedDateTime when timezone awareness is needed.""",
    },
    {
        "title": "DataWeave Type Coercion",
        "category": "dataweave",
        "content": """DataWeave Type Coercion (as) -> Java Type Conversion

MuleSoft DataWeave:
```xml
<ee:transform>
    <ee:set-payload><![CDATA[%dw 2.0
output application/json
---
{
    stringVal: payload.count as String,
    intVal: payload.amount as Number,
    dateVal: payload.dateStr as Date {format: "yyyy-MM-dd"},
    boolVal: payload.flag as Boolean
}]]></ee:set-payload>
</ee:transform>
```

Spring Boot Java:
```java
String stringVal = String.valueOf(data.getCount());
int intVal = Integer.parseInt(data.getAmount());
BigDecimal decimalVal = new BigDecimal(data.getAmount());
LocalDate dateVal = LocalDate.parse(data.getDateStr(), DateTimeFormatter.ofPattern("yyyy-MM-dd"));
boolean boolVal = Boolean.parseBoolean(data.getFlag());
```

Key mapping rules:
- DataWeave as String maps to String.valueOf() or .toString().
- DataWeave as Number maps to Integer.parseInt(), Double.parseDouble(), or new BigDecimal().
- DataWeave as Date with format maps to LocalDate.parse() with DateTimeFormatter.
- DataWeave as Boolean maps to Boolean.parseBoolean().
- Handle NumberFormatException and DateTimeParseException for invalid inputs.""",
    },
    {
        "title": "DataWeave Null Handling default operator",
        "category": "dataweave",
        "content": """DataWeave Null Handling (default) -> Java Optional.orElse

MuleSoft DataWeave:
```xml
<ee:transform>
    <ee:set-payload><![CDATA[%dw 2.0
output application/json
---
{
    name: payload.name default "Unknown",
    status: payload.status default "PENDING",
    items: payload.items default [],
    count: payload.count default 0
}]]></ee:set-payload>
</ee:transform>
```

Spring Boot Java:
```java
import java.util.Optional;
import java.util.Objects;

String name = Optional.ofNullable(data.getName()).orElse("Unknown");
String status = Objects.requireNonNullElse(data.getStatus(), "PENDING");
List<Item> items = Optional.ofNullable(data.getItems()).orElse(Collections.emptyList());
int count = data.getCount() != null ? data.getCount() : 0;
```

Key mapping rules:
- DataWeave default operator maps to Optional.orElse() or ternary operator.
- default "" maps to Optional.ofNullable(x).orElse("").
- default [] maps to Optional.ofNullable(list).orElse(Collections.emptyList()).
- Objects.requireNonNullElse() is a concise alternative for non-null defaults.
- For method chaining safety, use Optional.map().orElse().""",
    },
    {
        "title": "DataWeave if else to Java ternary",
        "category": "dataweave",
        "content": """DataWeave if/else -> Java Ternary Operator / if-else

MuleSoft DataWeave:
```xml
<ee:transform>
    <ee:set-payload><![CDATA[%dw 2.0
output application/json
---
{
    tier: if (payload.totalSpend > 10000) "GOLD"
         else if (payload.totalSpend > 5000) "SILVER"
         else "BRONZE",
    discount: if (payload.isMember) 0.15 else 0.0
}]]></ee:set-payload>
</ee:transform>
```

Spring Boot Java:
```java
String tier = customer.getTotalSpend().compareTo(BigDecimal.valueOf(10000)) > 0 ? "GOLD"
    : customer.getTotalSpend().compareTo(BigDecimal.valueOf(5000)) > 0 ? "SILVER"
    : "BRONZE";

double discount = customer.isMember() ? 0.15 : 0.0;
```

Key mapping rules:
- DataWeave if/else maps to Java ternary operator for simple conditions.
- Nested if/else chains map to chained ternary or regular if/else blocks.
- For complex logic with many branches, prefer if-else blocks or switch.
- DataWeave conditional assignment is expression-based, just like Java ternary.""",
    },
    {
        "title": "DataWeave Pattern Matching match case",
        "category": "dataweave",
        "content": """DataWeave match/case -> Java Switch Expression

MuleSoft DataWeave:
```xml
<ee:transform>
    <ee:set-payload><![CDATA[%dw 2.0
output application/json
---
payload.status match {
    case "NEW" -> {label: "New Order", color: "blue"}
    case "PROCESSING" -> {label: "In Progress", color: "yellow"}
    case "SHIPPED" -> {label: "Shipped", color: "green"}
    case "CANCELLED" -> {label: "Cancelled", color: "red"}
    else -> {label: "Unknown", color: "gray"}
}]]></ee:set-payload>
</ee:transform>
```

Spring Boot Java (switch expression, Java 14+):
```java
StatusInfo info = switch (order.getStatus()) {
    case "NEW" -> new StatusInfo("New Order", "blue");
    case "PROCESSING" -> new StatusInfo("In Progress", "yellow");
    case "SHIPPED" -> new StatusInfo("Shipped", "green");
    case "CANCELLED" -> new StatusInfo("Cancelled", "red");
    default -> new StatusInfo("Unknown", "gray");
};
```

Key mapping rules:
- DataWeave match/case maps to Java switch expression (Java 14+).
- The else clause maps to the default case.
- Each case returns a value, making it an expression not a statement.
- For pattern matching on types, use Java 16+ instanceof pattern matching.""",
    },
    # ==================================================================
    #  4. Connector Patterns (25 docs)
    # ==================================================================
    {
        "title": "VM Connector to Spring Events",
        "category": "connector",
        "content": """MuleSoft VM Connector -> Spring ApplicationEvent / @EventListener

MuleSoft XML:
```xml
<vm:config name="VM_Config">
    <vm:queues>
        <vm:queue queueName="orderQueue" queueType="TRANSIENT"/>
    </vm:queues>
</vm:config>
<flow name="publishOrderEvent">
    <vm:publish config-ref="VM_Config" queueName="orderQueue">
        <vm:content>#[payload]</vm:content>
    </vm:publish>
</flow>
<flow name="processOrderEvent">
    <vm:listener config-ref="VM_Config" queueName="orderQueue"/>
    <logger message="Processing order event: #[payload]"/>
</flow>
```

Spring Boot Java:
```java
// Event class
public class OrderCreatedEvent extends ApplicationEvent {
    private final OrderDTO order;
    public OrderCreatedEvent(Object source, OrderDTO order) {
        super(source);
        this.order = order;
    }
    public OrderDTO getOrder() { return order; }
}

// Publisher
@Service
public class OrderService {
    private final ApplicationEventPublisher eventPublisher;
    public OrderService(ApplicationEventPublisher eventPublisher) {
        this.eventPublisher = eventPublisher;
    }
    public void createOrder(CreateOrderRequest req) {
        OrderDTO order = saveOrder(req);
        eventPublisher.publishEvent(new OrderCreatedEvent(this, order));
    }
}

// Listener
@Component
@Slf4j
public class OrderEventListener {
    @EventListener
    public void handleOrderCreated(OrderCreatedEvent event) {
        log.info("Processing order event: {}", event.getOrder());
    }
}
```

Key mapping rules:
- MuleSoft VM publish maps to ApplicationEventPublisher.publishEvent().
- VM listener maps to @EventListener annotated method.
- VM queues with TRANSIENT type map to synchronous Spring events.
- For async processing, add @Async on the listener method.""",
    },
    {
        "title": "JMS Connector to Spring JMS",
        "category": "connector",
        "content": """MuleSoft JMS Connector -> Spring @JmsListener + JmsTemplate

MuleSoft XML:
```xml
<jms:config name="JMS_Config">
    <jms:active-mq-connection>
        <jms:factory-configuration brokerUrl="tcp://localhost:61616"/>
    </jms:active-mq-connection>
</jms:config>
<flow name="sendToQueue">
    <jms:publish config-ref="JMS_Config" destination="order.queue">
        <jms:body>#[output application/json --- payload]</jms:body>
    </jms:publish>
</flow>
<flow name="consumeFromQueue">
    <jms:listener config-ref="JMS_Config" destination="order.queue"/>
    <logger message="Received JMS message: #[payload]"/>
</flow>
```

Spring Boot Java:
```java
@Service
public class OrderMessageService {
    private final JmsTemplate jmsTemplate;
    public OrderMessageService(JmsTemplate jmsTemplate) {
        this.jmsTemplate = jmsTemplate;
    }
    public void sendOrder(OrderDTO order) {
        jmsTemplate.convertAndSend("order.queue", order);
    }
}

@Component
@Slf4j
public class OrderMessageListener {
    @JmsListener(destination = "order.queue")
    public void onMessage(OrderDTO order) {
        log.info("Received JMS message: {}", order);
    }
}
```

application.yml:
```yaml
spring:
  activemq:
    broker-url: tcp://localhost:61616
  jms:
    listener:
      concurrency: 3-10
```

Key mapping rules:
- MuleSoft jms:publish maps to JmsTemplate.convertAndSend().
- jms:listener maps to @JmsListener annotation.
- JMS connection config maps to spring.activemq properties.
- Message serialization is handled by Jackson message converter.""",
    },
    {
        "title": "AMQP RabbitMQ Connector to Spring RabbitMQ",
        "category": "connector",
        "content": """MuleSoft AMQP Connector -> Spring @RabbitListener + RabbitTemplate

MuleSoft XML:
```xml
<amqp:config name="AMQP_Config">
    <amqp:connection host="localhost" port="5672" username="guest" password="guest"/>
</amqp:config>
<flow name="publishToExchange">
    <amqp:publish config-ref="AMQP_Config" exchangeName="orders.exchange" routingKey="order.created">
        <amqp:body>#[output application/json --- payload]</amqp:body>
    </amqp:publish>
</flow>
<flow name="consumeFromQueue">
    <amqp:listener config-ref="AMQP_Config" queueName="orders.queue"/>
    <logger message="AMQP message: #[payload]"/>
</flow>
```

Spring Boot Java:
```java
@Service
public class OrderPublisher {
    private final RabbitTemplate rabbitTemplate;
    public void publishOrder(OrderDTO order) {
        rabbitTemplate.convertAndSend("orders.exchange", "order.created", order);
    }
}

@Component
@Slf4j
public class OrderConsumer {
    @RabbitListener(queues = "orders.queue")
    public void onMessage(OrderDTO order) {
        log.info("AMQP message: {}", order);
    }
}

@Configuration
public class RabbitConfig {
    @Bean
    public TopicExchange ordersExchange() {
        return new TopicExchange("orders.exchange");
    }
    @Bean
    public Queue ordersQueue() {
        return new Queue("orders.queue", true);
    }
    @Bean
    public Binding binding(Queue queue, TopicExchange exchange) {
        return BindingBuilder.bind(queue).to(exchange).with("order.*");
    }
}
```

Key mapping rules:
- MuleSoft amqp:publish maps to RabbitTemplate.convertAndSend().
- amqp:listener maps to @RabbitListener annotation.
- Exchange, queue, and binding declarations go in @Configuration.
- AMQP connection config maps to spring.rabbitmq properties in YAML.""",
    },
    {
        "title": "Kafka Connector to Spring Kafka",
        "category": "connector",
        "content": """MuleSoft Kafka Connector -> Spring @KafkaListener + KafkaTemplate

MuleSoft XML:
```xml
<kafka:consumer-config name="Kafka_Consumer" topic="orders">
    <kafka:consumer-plaintext-connection bootstrapServers="localhost:9092" groupId="order-service"/>
</kafka:consumer-config>
<kafka:producer-config name="Kafka_Producer" topic="order-events">
    <kafka:producer-plaintext-connection bootstrapServers="localhost:9092"/>
</kafka:producer-config>
<flow name="consumeKafka">
    <kafka:message-listener config-ref="Kafka_Consumer"/>
    <logger message="Kafka message: #[payload]"/>
</flow>
<flow name="produceKafka">
    <kafka:publish config-ref="Kafka_Producer" topic="order-events" key="#[payload.orderId]">
        <kafka:message>#[output application/json --- payload]</kafka:message>
    </kafka:publish>
</flow>
```

Spring Boot Java:
```java
@Component
@Slf4j
public class OrderKafkaConsumer {
    @KafkaListener(topics = "orders", groupId = "order-service")
    public void consume(OrderDTO order) {
        log.info("Kafka message: {}", order);
    }
}

@Service
public class OrderKafkaProducer {
    private final KafkaTemplate<String, OrderDTO> kafkaTemplate;
    public void publish(OrderDTO order) {
        kafkaTemplate.send("order-events", order.getOrderId(), order);
    }
}
```

application.yml:
```yaml
spring:
  kafka:
    bootstrap-servers: localhost:9092
    consumer:
      group-id: order-service
      auto-offset-reset: earliest
    producer:
      key-serializer: org.apache.kafka.common.serialization.StringSerializer
      value-serializer: org.springframework.kafka.support.serializer.JsonSerializer
```

Key mapping rules:
- MuleSoft kafka:message-listener maps to @KafkaListener.
- kafka:publish maps to KafkaTemplate.send().
- Bootstrap servers and group ID map to spring.kafka properties.
- Message serialization is configured via YAML or @Bean configuration.""",
    },
    {
        "title": "File Connector Read to Java NIO",
        "category": "connector",
        "content": """MuleSoft File Connector Read -> Java NIO Files / ResourceLoader

MuleSoft XML:
```xml
<file:config name="File_Config">
    <file:connection workingDir="/data/input"/>
</file:config>
<flow name="readFileFlow">
    <file:read config-ref="File_Config" path="orders.csv"/>
    <logger message="File content: #[payload]"/>
</flow>
```

Spring Boot Java:
```java
@Service
@Slf4j
public class FileReaderService {
    public String readFile(String fileName) throws IOException {
        Path path = Path.of("/data/input", fileName);
        String content = Files.readString(path);
        log.info("File content length: {}", content.length());
        return content;
    }

    public List<String> readLines(String fileName) throws IOException {
        Path path = Path.of("/data/input", fileName);
        return Files.readAllLines(path);
    }
}
```

Key mapping rules:
- MuleSoft file:read maps to java.nio.file.Files.readString() or readAllLines().
- File connection workingDir maps to a base path in configuration.
- For classpath resources, use ResourceLoader.getResource().
- For large files, use Files.lines() for lazy streaming to avoid memory issues.""",
    },
    {
        "title": "File Connector Write to Java NIO",
        "category": "connector",
        "content": """MuleSoft File Connector Write -> Java NIO Files.write

MuleSoft XML:
```xml
<flow name="writeFileFlow">
    <file:write config-ref="File_Config" path="output/report.csv" mode="OVERWRITE">
        <file:content>#[payload]</file:content>
    </file:write>
</flow>
```

Spring Boot Java:
```java
@Service
public class FileWriterService {
    @Value("${app.output.dir:/data/output}")
    private String outputDir;

    public void writeFile(String fileName, String content) throws IOException {
        Path dir = Path.of(outputDir);
        Files.createDirectories(dir);
        Path file = dir.resolve(fileName);
        Files.writeString(file, content, StandardOpenOption.CREATE, StandardOpenOption.TRUNCATE_EXISTING);
    }

    public void appendToFile(String fileName, String content) throws IOException {
        Path file = Path.of(outputDir, fileName);
        Files.writeString(file, content, StandardOpenOption.CREATE, StandardOpenOption.APPEND);
    }
}
```

Key mapping rules:
- MuleSoft file:write with OVERWRITE maps to Files.writeString with TRUNCATE_EXISTING.
- file:write with APPEND maps to StandardOpenOption.APPEND.
- Always create parent directories with Files.createDirectories().
- Configure output paths via application.yml, not hard-coded.""",
    },
    {
        "title": "File Connector Watch to WatchService",
        "category": "connector",
        "content": """MuleSoft File Connector Listener -> Java WatchService

MuleSoft XML:
```xml
<flow name="fileListenerFlow">
    <file:listener config-ref="File_Config" directory="/data/input" autoDelete="true">
        <scheduling-strategy>
            <fixed-frequency frequency="5000"/>
        </scheduling-strategy>
        <file:matcher filenamePattern="*.csv"/>
    </file:listener>
    <logger message="New file: #[attributes.fileName]"/>
</flow>
```

Spring Boot Java:
```java
@Service
@Slf4j
public class FileWatcherService {
    @Value("${app.watch.dir:/data/input}")
    private String watchDir;

    @Scheduled(fixedDelay = 5000)
    public void pollForFiles() throws IOException {
        Path dir = Path.of(watchDir);
        try (DirectoryStream<Path> stream = Files.newDirectoryStream(dir, "*.csv")) {
            for (Path file : stream) {
                log.info("New file: {}", file.getFileName());
                processFile(file);
                Files.delete(file); // autoDelete equivalent
            }
        }
    }
}
```

Key mapping rules:
- MuleSoft file:listener maps to @Scheduled polling with DirectoryStream.
- filenamePattern maps to the glob pattern in newDirectoryStream().
- autoDelete=true maps to Files.delete() after processing.
- fixed-frequency scheduling maps to @Scheduled(fixedDelay=5000).""",
    },
    {
        "title": "FTP Connector to Apache Commons Net",
        "category": "connector",
        "content": """MuleSoft FTP Connector -> Apache Commons Net FTPClient

MuleSoft XML:
```xml
<ftp:config name="FTP_Config">
    <ftp:connection host="ftp.example.com" port="21" username="${ftp.user}" password="${ftp.password}" workingDir="/remote/data"/>
</ftp:config>
<flow name="readFtpFile">
    <ftp:read config-ref="FTP_Config" path="data.csv"/>
</flow>
<flow name="writeFtpFile">
    <ftp:write config-ref="FTP_Config" path="output/report.csv">
        <ftp:content>#[payload]</ftp:content>
    </ftp:write>
</flow>
```

Spring Boot Java:
```java
@Service
@Slf4j
public class FtpService {
    @Value("${ftp.host}") private String host;
    @Value("${ftp.username}") private String username;
    @Value("${ftp.password}") private String password;

    public String readFile(String remotePath) throws IOException {
        FTPClient ftp = new FTPClient();
        try {
            ftp.connect(host, 21);
            ftp.login(username, password);
            ftp.enterLocalPassiveMode();
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            ftp.retrieveFile(remotePath, out);
            return out.toString(StandardCharsets.UTF_8);
        } finally {
            if (ftp.isConnected()) { ftp.logout(); ftp.disconnect(); }
        }
    }

    public void writeFile(String remotePath, String content) throws IOException {
        FTPClient ftp = new FTPClient();
        try {
            ftp.connect(host, 21);
            ftp.login(username, password);
            ftp.enterLocalPassiveMode();
            ftp.storeFile(remotePath, new ByteArrayInputStream(content.getBytes()));
        } finally {
            if (ftp.isConnected()) { ftp.logout(); ftp.disconnect(); }
        }
    }
}
```

Key mapping rules:
- MuleSoft ftp:read maps to FTPClient.retrieveFile().
- ftp:write maps to FTPClient.storeFile().
- FTP connection config maps to @Value properties.
- Always use try-finally to ensure disconnect.""",
    },
    {
        "title": "SFTP Connector to Spring Integration SFTP",
        "category": "connector",
        "content": """MuleSoft SFTP Connector -> JSch / Spring Integration SFTP

MuleSoft XML:
```xml
<sftp:config name="SFTP_Config">
    <sftp:connection host="sftp.example.com" port="22" username="${sftp.user}" password="${sftp.password}" workingDir="/remote"/>
</sftp:config>
<flow name="sftpReadFlow">
    <sftp:read config-ref="SFTP_Config" path="data/input.csv"/>
</flow>
```

Spring Boot Java (Spring Integration):
```java
@Configuration
public class SftpConfig {
    @Bean
    public SessionFactory<SftpClient.DirEntry> sftpSessionFactory() {
        DefaultSftpSessionFactory factory = new DefaultSftpSessionFactory();
        factory.setHost("sftp.example.com");
        factory.setPort(22);
        factory.setUser("${sftp.user}");
        factory.setPassword("${sftp.password}");
        factory.setAllowUnknownKeys(true);
        return factory;
    }

    @Bean
    public SftpRemoteFileTemplate sftpTemplate(SessionFactory<SftpClient.DirEntry> sf) {
        return new SftpRemoteFileTemplate(sf);
    }
}

@Service
public class SftpService {
    private final SftpRemoteFileTemplate sftpTemplate;

    public String readFile(String remotePath) {
        return sftpTemplate.execute(session -> {
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            session.read(remotePath, out);
            return out.toString(StandardCharsets.UTF_8);
        });
    }
}
```

Key mapping rules:
- MuleSoft sftp:config maps to DefaultSftpSessionFactory @Bean.
- sftp:read maps to SftpRemoteFileTemplate.execute() with session.read().
- Connection properties map to factory setters or application.yml.
- For file polling, use @InboundChannelAdapter with SftpInboundFileSynchronizer.""",
    },
    {
        "title": "Email Connector SMTP to JavaMailSender",
        "category": "connector",
        "content": """MuleSoft Email SMTP Connector -> Spring Boot JavaMailSender

MuleSoft XML:
```xml
<email:smtp-config name="SMTP_Config">
    <email:smtps-connection host="smtp.gmail.com" port="465" user="${email.user}" password="${email.password}"/>
</email:smtp-config>
<flow name="sendEmailFlow">
    <email:send config-ref="SMTP_Config">
        <email:to-addresses>
            <email:to-address value="#[payload.to]"/>
        </email:to-addresses>
        <email:body contentType="text/html">
            <email:content>#[payload.body]</email:content>
        </email:body>
        <email:subject>#[payload.subject]</email:subject>
    </email:send>
</flow>
```

Spring Boot Java:
```java
@Service
@Slf4j
public class EmailService {
    private final JavaMailSender mailSender;

    public void sendEmail(String to, String subject, String htmlBody) {
        MimeMessage message = mailSender.createMimeMessage();
        try {
            MimeMessageHelper helper = new MimeMessageHelper(message, true);
            helper.setTo(to);
            helper.setSubject(subject);
            helper.setText(htmlBody, true);
            mailSender.send(message);
            log.info("Email sent to {}", to);
        } catch (MessagingException e) {
            throw new EmailSendException("Failed to send email", e);
        }
    }
}
```

application.yml:
```yaml
spring:
  mail:
    host: smtp.gmail.com
    port: 465
    username: ${EMAIL_USER}
    password: ${EMAIL_PASSWORD}
    properties:
      mail.smtp.ssl.enable: true
```

Key mapping rules:
- MuleSoft email:smtp-config maps to spring.mail properties.
- email:send maps to JavaMailSender.send() with MimeMessageHelper.
- HTML content type maps to helper.setText(body, true).
- For attachments, use helper.addAttachment().""",
    },
    {
        "title": "Email Connector IMAP to Spring Integration Mail",
        "category": "connector",
        "content": """MuleSoft Email IMAP Listener -> Spring Integration Mail

MuleSoft XML:
```xml
<email:imap-config name="IMAP_Config">
    <email:imaps-connection host="imap.gmail.com" port="993" user="${email.user}" password="${email.password}"/>
</email:imap-config>
<flow name="receiveEmailFlow">
    <email:listener-imap config-ref="IMAP_Config" folder="INBOX">
        <scheduling-strategy><fixed-frequency frequency="60000"/></scheduling-strategy>
    </email:listener-imap>
    <logger message="New email from: #[attributes.fromAddresses]"/>
</flow>
```

Spring Boot Java:
```java
@Configuration
public class MailReceiverConfig {
    @Bean
    public IntegrationFlow imapFlow() {
        return IntegrationFlow.from(
            Mail.imapInboundAdapter("imaps://user:pass@imap.gmail.com:993/INBOX")
                .shouldDeleteMessages(false)
                .shouldMarkMessagesAsRead(true),
            e -> e.poller(Pollers.fixedDelay(60000)))
            .handle(message -> {
                MimeMessage mail = (MimeMessage) message.getPayload();
                log.info("New email from: {}", mail.getFrom()[0]);
            })
            .get();
    }
}
```

Key mapping rules:
- MuleSoft email:listener-imap maps to Mail.imapInboundAdapter() in Spring Integration.
- Polling frequency maps to Pollers.fixedDelay().
- Email attributes (from, subject, etc.) are available on the MimeMessage object.
- Configure IMAP credentials via application.yml with environment variables.""",
    },
    {
        "title": "Salesforce Connector to REST API with WebClient",
        "category": "connector",
        "content": """MuleSoft Salesforce Connector -> REST API with WebClient

MuleSoft XML:
```xml
<salesforce:sfdc-config name="Salesforce_Config">
    <salesforce:basic-connection username="${sf.username}" password="${sf.password}" securityToken="${sf.token}"/>
</salesforce:sfdc-config>
<flow name="querySalesforce">
    <salesforce:query config-ref="Salesforce_Config">
        <salesforce:salesforce-query>SELECT Id, Name, Email FROM Contact WHERE AccountId = ':accountId'</salesforce:salesforce-query>
        <salesforce:parameters><![CDATA[#[{accountId: vars.accountId}]]]></salesforce:parameters>
    </salesforce:query>
</flow>
```

Spring Boot Java:
```java
@Service
public class SalesforceService {
    private final WebClient webClient;
    private final SalesforceAuthService authService;

    public List<SfContact> queryContacts(String accountId) {
        String token = authService.getAccessToken();
        String soql = "SELECT Id, Name, Email FROM Contact WHERE AccountId = '" + accountId + "'";
        SfQueryResult result = webClient.get()
            .uri(uriBuilder -> uriBuilder.path("/services/data/v58.0/query")
                .queryParam("q", soql).build())
            .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
            .retrieve()
            .bodyToMono(SfQueryResult.class)
            .block();
        return result.getRecords();
    }
}

@Service
public class SalesforceAuthService {
    public String getAccessToken() {
        // OAuth2 password grant or JWT bearer flow
        MultiValueMap<String, String> params = new LinkedMultiValueMap<>();
        params.add("grant_type", "password");
        params.add("client_id", clientId);
        params.add("client_secret", clientSecret);
        params.add("username", username);
        params.add("password", password + securityToken);
        SfAuthResponse auth = webClient.post()
            .uri("https://login.salesforce.com/services/oauth2/token")
            .bodyValue(params).retrieve()
            .bodyToMono(SfAuthResponse.class).block();
        return auth.getAccessToken();
    }
}
```

Key mapping rules:
- MuleSoft Salesforce connector maps to REST API calls via WebClient.
- SOQL queries map to /services/data/vXX.0/query endpoint.
- Salesforce authentication maps to OAuth2 token endpoint.
- Create dedicated SalesforceService and SalesforceAuthService classes.""",
    },
    {
        "title": "SOAP Web Service Consumer to JAX-WS",
        "category": "connector",
        "content": """MuleSoft Web Service Consumer -> Spring WebServiceTemplate / JAX-WS

MuleSoft XML:
```xml
<wsc:config name="WSC_Config">
    <wsc:connection wsdlLocation="http://example.com/service?wsdl" service="OrderService" port="OrderPort"
        address="http://example.com/service"/>
</wsc:config>
<flow name="callSoapService">
    <wsc:consume config-ref="WSC_Config" operation="getOrder">
        <wsc:message>
            <wsc:body>#[output application/xml --- { getOrderRequest: { orderId: vars.orderId } }]</wsc:body>
        </wsc:message>
    </wsc:consume>
</flow>
```

Spring Boot Java:
```java
@Configuration
public class SoapClientConfig {
    @Bean
    public Jaxb2Marshaller marshaller() {
        Jaxb2Marshaller marshaller = new Jaxb2Marshaller();
        marshaller.setContextPath("com.example.generated");
        return marshaller;
    }

    @Bean
    public WebServiceTemplate webServiceTemplate(Jaxb2Marshaller marshaller) {
        WebServiceTemplate template = new WebServiceTemplate();
        template.setDefaultUri("http://example.com/service");
        template.setMarshaller(marshaller);
        template.setUnmarshaller(marshaller);
        return template;
    }
}

@Service
public class OrderSoapClient {
    private final WebServiceTemplate wsTemplate;

    public GetOrderResponse getOrder(String orderId) {
        GetOrderRequest request = new GetOrderRequest();
        request.setOrderId(orderId);
        return (GetOrderResponse) wsTemplate.marshalSendAndReceive(request);
    }
}
```

Key mapping rules:
- MuleSoft wsc:config with WSDL maps to WebServiceTemplate bean.
- wsc:consume maps to wsTemplate.marshalSendAndReceive().
- Generate Java classes from WSDL using jaxb2-maven-plugin.
- Jaxb2Marshaller handles XML serialization/deserialization.""",
    },
    {
        "title": "REST API Consumer to WebClient",
        "category": "connector",
        "content": """MuleSoft HTTP Request (API Consumer) -> Spring Boot WebClient

MuleSoft XML:
```xml
<http:request-config name="Payment_API">
    <http:request-connection host="payment-api.example.com" port="443" protocol="HTTPS"/>
</http:request-config>
<flow name="processPayment">
    <http:request config-ref="Payment_API" path="/v1/payments" method="POST">
        <http:body><![CDATA[#[output application/json --- {
            amount: payload.amount,
            currency: payload.currency,
            customerId: payload.customerId
        }]]]></http:body>
    </http:request>
</flow>
```

Spring Boot Java:
```java
@Service
@Slf4j
public class PaymentApiClient {
    private final WebClient webClient;

    public PaymentApiClient(@Value("${payment.api.base-url}") String baseUrl) {
        this.webClient = WebClient.builder()
            .baseUrl(baseUrl)
            .defaultHeader(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
            .build();
    }

    public PaymentResponse processPayment(PaymentRequest request) {
        return webClient.post()
            .uri("/v1/payments")
            .bodyValue(request)
            .retrieve()
            .onStatus(HttpStatusCode::is4xxClientError, resp ->
                resp.bodyToMono(String.class).map(PaymentException::new))
            .bodyToMono(PaymentResponse.class)
            .block();
    }
}
```

Key mapping rules:
- MuleSoft http:request-config maps to WebClient.builder().baseUrl().
- http:request POST with body maps to webClient.post().bodyValue().
- DataWeave JSON output maps to Java DTO serialized by Jackson.
- Add error handling with onStatus() for HTTP error responses.""",
    },
    {
        "title": "Object Store to Spring Cache and Redis",
        "category": "connector",
        "content": """MuleSoft Object Store -> Spring Cache (@Cacheable) / Redis

MuleSoft XML:
```xml
<os:object-store name="tokenStore" persistent="true" entryTtl="3600" entryTtlUnit="SECONDS"/>
<flow name="cacheTokenFlow">
    <os:store key="#[vars.clientId]" objectStore="tokenStore">
        <os:value>#[vars.token]</os:value>
    </os:store>
</flow>
<flow name="retrieveTokenFlow">
    <os:retrieve key="#[vars.clientId]" objectStore="tokenStore" target="token"/>
</flow>
```

Spring Boot Java:
```java
@Service
public class TokenService {
    @Cacheable(value = "tokens", key = "#clientId")
    public String getToken(String clientId) {
        return generateNewToken(clientId);
    }

    @CacheEvict(value = "tokens", key = "#clientId")
    public void invalidateToken(String clientId) {}
}

@Configuration
@EnableCaching
public class CacheConfig {
    @Bean
    public RedisCacheManager cacheManager(RedisConnectionFactory factory) {
        RedisCacheConfiguration config = RedisCacheConfiguration.defaultCacheConfig()
            .entryTtl(Duration.ofSeconds(3600));
        return RedisCacheManager.builder(factory)
            .cacheDefaults(config).build();
    }
}
```

application.yml:
```yaml
spring:
  cache:
    type: redis
  redis:
    host: localhost
    port: 6379
```

Key mapping rules:
- MuleSoft os:store maps to @Cacheable or RedisTemplate.opsForValue().set().
- os:retrieve maps to cache lookup or RedisTemplate.opsForValue().get().
- entryTtl maps to RedisCacheConfiguration.entryTtl().
- persistent=true maps to Redis (vs. in-memory ConcurrentMapCache).""",
    },
    {
        "title": "Scheduler to Spring @Scheduled",
        "category": "connector",
        "content": """MuleSoft Scheduler -> Spring Boot @Scheduled

MuleSoft XML:
```xml
<flow name="scheduledReportFlow">
    <scheduler>
        <scheduling-strategy>
            <cron expression="0 0 8 * * MON-FRI" timeZone="America/New_York"/>
        </scheduling-strategy>
    </scheduler>
    <logger message="Running scheduled report"/>
    <flow-ref name="generateReportSubflow"/>
</flow>
<flow name="pollingFlow">
    <scheduler>
        <scheduling-strategy>
            <fixed-frequency frequency="30000"/>
        </scheduling-strategy>
    </scheduler>
    <logger message="Polling for updates"/>
</flow>
```

Spring Boot Java:
```java
@Component
@Slf4j
public class ScheduledTasks {

    private final ReportService reportService;

    @Scheduled(cron = "0 0 8 * * MON-FRI", zone = "America/New_York")
    public void generateDailyReport() {
        log.info("Running scheduled report");
        reportService.generateReport();
    }

    @Scheduled(fixedDelay = 30000)
    public void pollForUpdates() {
        log.info("Polling for updates");
    }
}

@Configuration
@EnableScheduling
public class SchedulingConfig {}
```

Key mapping rules:
- MuleSoft scheduler with cron maps to @Scheduled(cron = "...").
- fixed-frequency maps to @Scheduled(fixedDelay = ...) in milliseconds.
- Cron format is the same (6 fields: sec min hour day month weekday).
- Enable scheduling with @EnableScheduling on a config class.
- timeZone maps to zone parameter.""",
    },
    {
        "title": "Batch Job to Spring Batch",
        "category": "connector",
        "content": """MuleSoft Batch Job -> Spring Batch

MuleSoft XML:
```xml
<batch:job name="importProductsBatch" maxFailedRecords="10">
    <batch:process-records>
        <batch:step name="validateStep">
            <batch:step-processor>
                <validation:is-not-null value="#[payload.name]"/>
            </batch:step-processor>
        </batch:step>
        <batch:step name="transformStep">
            <ee:transform>
                <ee:set-payload><![CDATA[%dw 2.0
output application/java
---
payload]]></ee:set-payload>
            </ee:transform>
        </batch:step>
        <batch:step name="loadStep">
            <db:insert config-ref="Database_Config">
                <db:sql>INSERT INTO products (name, price) VALUES (:name, :price)</db:sql>
                <db:input-parameters><![CDATA[#[{name: payload.name, price: payload.price}]]]></db:input-parameters>
            </db:insert>
        </batch:step>
    </batch:process-records>
    <batch:on-complete>
        <logger message="Batch complete: #[payload.processedRecords] processed"/>
    </batch:on-complete>
</batch:job>
```

Spring Boot Java:
```java
@Configuration
@EnableBatchProcessing
public class BatchConfig {
    @Bean
    public Job importProductsJob(JobRepository jobRepository, Step processStep) {
        return new JobBuilder("importProductsBatch", jobRepository)
            .start(processStep).build();
    }

    @Bean
    public Step processStep(JobRepository jobRepository, PlatformTransactionManager txMgr,
            ItemReader<ProductCsv> reader, ItemProcessor<ProductCsv, Product> processor,
            ItemWriter<Product> writer) {
        return new StepBuilder("processStep", jobRepository)
            .<ProductCsv, Product>chunk(100, txMgr)
            .reader(reader).processor(processor).writer(writer)
            .faultTolerant().skipLimit(10).skip(ValidationException.class)
            .build();
    }

    @Bean
    public ItemProcessor<ProductCsv, Product> processor() {
        return item -> {
            if (item.getName() == null) throw new ValidationException("Name required");
            return new Product(item.getName(), item.getPrice());
        };
    }

    @Bean
    public JdbcBatchItemWriter<Product> writer(DataSource ds) {
        return new JdbcBatchItemWriterBuilder<Product>()
            .sql("INSERT INTO products (name, price) VALUES (:name, :price)")
            .dataSource(ds).beanMapped().build();
    }
}
```

Key mapping rules:
- MuleSoft batch:job maps to Spring Batch Job.
- batch:step maps to Step with reader-processor-writer pattern.
- maxFailedRecords maps to .faultTolerant().skipLimit().
- batch:on-complete maps to JobExecutionListener.afterJob().
- Chunk-based processing is the standard Spring Batch pattern.""",
    },
    {
        "title": "Watermark Polling to Scheduled State Tracking",
        "category": "connector",
        "content": """MuleSoft Watermark / Polling -> @Scheduled + State Tracking

MuleSoft XML:
```xml
<flow name="pollNewOrdersFlow">
    <db:listener config-ref="Database_Config" table="orders" watermarkColumn="updated_at" idColumn="id">
        <scheduling-strategy>
            <fixed-frequency frequency="60000"/>
        </scheduling-strategy>
    </db:listener>
    <logger message="New/updated order: #[payload]"/>
</flow>
```

Spring Boot Java:
```java
@Service
@Slf4j
public class OrderPollingService {
    private final OrderRepository orderRepository;
    private LocalDateTime lastPollTime = LocalDateTime.now().minusMinutes(5);

    @Scheduled(fixedDelay = 60000)
    @Transactional(readOnly = true)
    public void pollNewOrders() {
        LocalDateTime now = LocalDateTime.now();
        List<Order> newOrders = orderRepository.findByUpdatedAtAfter(lastPollTime);
        for (Order order : newOrders) {
            log.info("New/updated order: {}", order.getId());
            processOrder(order);
        }
        lastPollTime = now;
    }
}
```

Key mapping rules:
- MuleSoft watermarkColumn maps to tracking the last poll timestamp.
- db:listener with polling maps to @Scheduled with a query using timestamp comparison.
- Store the watermark in memory, database, or Redis for persistence across restarts.
- Use @Transactional(readOnly = true) for poll queries.""",
    },
    {
        "title": "Anypoint MQ to Azure Service Bus",
        "category": "connector",
        "content": """MuleSoft Anypoint MQ -> Azure Service Bus / RabbitMQ

MuleSoft XML:
```xml
<anypoint-mq:config name="Anypoint_MQ_Config">
    <anypoint-mq:connection url="${anypoint.mq.url}" clientId="${anypoint.mq.clientId}" clientSecret="${anypoint.mq.clientSecret}"/>
</anypoint-mq:config>
<flow name="publishToMQ">
    <anypoint-mq:publish config-ref="Anypoint_MQ_Config" destination="order-queue">
        <anypoint-mq:body>#[output application/json --- payload]</anypoint-mq:body>
    </anypoint-mq:publish>
</flow>
<flow name="subscribeFromMQ">
    <anypoint-mq:subscriber config-ref="Anypoint_MQ_Config" destination="order-queue"/>
    <logger message="Received: #[payload]"/>
</flow>
```

Spring Boot Java (Azure Service Bus):
```java
@Service
public class MessagePublisher {
    private final ServiceBusSenderClient senderClient;

    public void publish(OrderDTO order) throws JsonProcessingException {
        ObjectMapper mapper = new ObjectMapper();
        ServiceBusMessage message = new ServiceBusMessage(mapper.writeValueAsString(order));
        senderClient.sendMessage(message);
    }
}

@Component
@Slf4j
public class MessageSubscriber {
    @ServiceBusListener(destination = "order-queue")
    public void onMessage(String messageBody) {
        log.info("Received: {}", messageBody);
    }
}
```

Key mapping rules:
- MuleSoft Anypoint MQ publish maps to ServiceBusSenderClient.sendMessage().
- Anypoint MQ subscriber maps to @ServiceBusListener or ServiceBusProcessorClient.
- MQ URL/credentials map to Azure Service Bus connection string.
- Alternative: use RabbitMQ with @RabbitListener as shown in AMQP pattern.""",
    },
    {
        "title": "LDAP Connector to Spring LDAP",
        "category": "connector",
        "content": """MuleSoft LDAP Connector -> Spring LDAP

MuleSoft XML:
```xml
<ldap:config name="LDAP_Config">
    <ldap:connection url="ldap://ldap.example.com:389" authDn="cn=admin,dc=example,dc=com" authPassword="${ldap.password}"/>
</ldap:config>
<flow name="searchLdap">
    <ldap:search config-ref="LDAP_Config" baseDn="ou=users,dc=example,dc=com" filter="(uid=#[vars.username])"/>
</flow>
```

Spring Boot Java:
```java
@Configuration
public class LdapConfig {
    @Bean
    public LdapContextSource contextSource() {
        LdapContextSource ctx = new LdapContextSource();
        ctx.setUrl("ldap://ldap.example.com:389");
        ctx.setUserDn("cn=admin,dc=example,dc=com");
        ctx.setPassword(ldapPassword);
        return ctx;
    }
    @Bean
    public LdapTemplate ldapTemplate(LdapContextSource ctx) {
        return new LdapTemplate(ctx);
    }
}

@Service
public class LdapUserService {
    private final LdapTemplate ldapTemplate;
    public LdapUser findByUsername(String username) {
        return ldapTemplate.findOne(
            LdapQueryBuilder.query()
                .base("ou=users,dc=example,dc=com")
                .filter("(uid={0})", username),
            LdapUser.class);
    }
}
```

Key mapping rules:
- MuleSoft ldap:config maps to LdapContextSource @Bean.
- ldap:search maps to LdapTemplate.search() or findOne().
- Search filter with parameters uses {0}, {1} placeholders.
- Use Spring LDAP's Object-Directory Mapping for entity-style access.""",
    },
    {
        "title": "MongoDB Connector to Spring Data MongoDB",
        "category": "connector",
        "content": """MuleSoft MongoDB Connector -> Spring Data MongoDB

MuleSoft XML:
```xml
<mongo:config name="MongoDB_Config">
    <mongo:connection host="localhost" port="27017" database="mydb" username="${mongo.user}" password="${mongo.password}"/>
</mongo:config>
<flow name="findDocuments">
    <mongo:find-documents config-ref="MongoDB_Config" collectionName="products">
        <mongo:query><![CDATA[#[{category: vars.category}]]]></mongo:query>
    </mongo:find-documents>
</flow>
<flow name="insertDocument">
    <mongo:insert-document config-ref="MongoDB_Config" collectionName="products">
        <mongo:document>#[output application/json --- payload]</mongo:document>
    </mongo:insert-document>
</flow>
```

Spring Boot Java:
```java
@Document(collection = "products")
public class Product {
    @Id private String id;
    private String name;
    private BigDecimal price;
    private String category;
}

public interface ProductRepository extends MongoRepository<Product, String> {
    List<Product> findByCategory(String category);
}

@Service
public class ProductService {
    private final ProductRepository repository;
    public List<Product> findByCategory(String category) {
        return repository.findByCategory(category);
    }
    public Product create(Product product) {
        return repository.save(product);
    }
}
```

application.yml:
```yaml
spring:
  data:
    mongodb:
      uri: mongodb://${MONGO_USER}:${MONGO_PASS}@localhost:27017/mydb
```

Key mapping rules:
- MuleSoft mongo:find-documents maps to MongoRepository derived queries.
- mongo:insert-document maps to repository.save().
- MongoDB config maps to spring.data.mongodb properties.
- Use @Document annotation instead of @Entity for MongoDB collections.""",
    },
    {
        "title": "Elasticsearch Connector to Spring Data Elasticsearch",
        "category": "connector",
        "content": """MuleSoft Elasticsearch Connector -> Spring Data Elasticsearch

MuleSoft XML:
```xml
<elasticsearch:config name="ES_Config">
    <elasticsearch:connection url="http://localhost:9200"/>
</elasticsearch:config>
<flow name="searchDocuments">
    <elasticsearch:search config-ref="ES_Config" index="products">
        <elasticsearch:query><![CDATA[{"query": {"match": {"name": "#[vars.searchTerm]"}}}]]></elasticsearch:query>
    </elasticsearch:search>
</flow>
```

Spring Boot Java:
```java
@Document(indexName = "products")
public class ProductDocument {
    @Id private String id;
    @Field(type = FieldType.Text) private String name;
    @Field(type = FieldType.Double) private Double price;
}

public interface ProductSearchRepository extends ElasticsearchRepository<ProductDocument, String> {
    List<ProductDocument> findByName(String name);
}

@Service
public class SearchService {
    private final ElasticsearchOperations operations;
    public List<ProductDocument> search(String term) {
        NativeQuery query = NativeQuery.builder()
            .withQuery(q -> q.match(m -> m.field("name").query(term)))
            .build();
        SearchHits<ProductDocument> hits = operations.search(query, ProductDocument.class);
        return hits.stream().map(SearchHit::getContent).collect(Collectors.toList());
    }
}
```

Key mapping rules:
- MuleSoft elasticsearch:search maps to ElasticsearchOperations.search().
- ES config maps to spring.elasticsearch properties.
- Use @Document(indexName) for index mapping.
- NativeQuery builder replaces raw JSON queries.""",
    },
    {
        "title": "Redis Connector to Spring Data Redis",
        "category": "connector",
        "content": """MuleSoft Redis Connector -> Spring Data Redis

MuleSoft XML:
```xml
<redis:config name="Redis_Config" host="localhost" port="6379"/>
<flow name="setRedisValue">
    <redis:set config-ref="Redis_Config" key="#[vars.key]" value="#[payload]"/>
</flow>
<flow name="getRedisValue">
    <redis:get config-ref="Redis_Config" key="#[vars.key]"/>
</flow>
```

Spring Boot Java:
```java
@Service
public class RedisService {
    private final StringRedisTemplate redisTemplate;

    public void set(String key, String value, Duration ttl) {
        redisTemplate.opsForValue().set(key, value, ttl);
    }

    public String get(String key) {
        return redisTemplate.opsForValue().get(key);
    }

    public void setHash(String key, Map<String, String> fields) {
        redisTemplate.opsForHash().putAll(key, fields);
    }
}
```

application.yml:
```yaml
spring:
  redis:
    host: localhost
    port: 6379
    password: ${REDIS_PASSWORD:}
    lettuce:
      pool:
        max-active: 10
        max-idle: 5
```

Key mapping rules:
- MuleSoft redis:set maps to RedisTemplate.opsForValue().set().
- redis:get maps to RedisTemplate.opsForValue().get().
- Redis config maps to spring.redis properties.
- Use StringRedisTemplate for string values; RedisTemplate for objects.""",
    },
    {
        "title": "AWS S3 Connector to Azure Blob Storage",
        "category": "connector",
        "content": """MuleSoft S3 Connector -> Azure Blob Storage SDK

MuleSoft XML:
```xml
<s3:config name="S3_Config" accessKey="${aws.accessKey}" secretKey="${aws.secretKey}" region="us-east-1"/>
<flow name="uploadToS3">
    <s3:put-object config-ref="S3_Config" bucketName="my-bucket" key="#[vars.fileName]">
        <s3:content>#[payload]</s3:content>
    </s3:put-object>
</flow>
<flow name="downloadFromS3">
    <s3:get-object config-ref="S3_Config" bucketName="my-bucket" key="#[vars.fileName]"/>
</flow>
```

Spring Boot Java (Azure Blob Storage):
```java
@Service
public class BlobStorageService {
    private final BlobServiceClient blobServiceClient;

    public String upload(String containerName, String blobName, byte[] data) {
        BlobContainerClient container = blobServiceClient.getBlobContainerClient(containerName);
        BlobClient blob = container.getBlobClient(blobName);
        blob.upload(BinaryData.fromBytes(data), true);
        return blob.getBlobUrl();
    }

    public byte[] download(String containerName, String blobName) {
        BlobClient blob = blobServiceClient.getBlobContainerClient(containerName)
            .getBlobClient(blobName);
        return blob.downloadContent().toBytes();
    }
}
```

Key mapping rules:
- MuleSoft S3 bucketName maps to Azure container name.
- s3:put-object maps to BlobClient.upload().
- s3:get-object maps to BlobClient.downloadContent().
- AWS credentials map to Azure connection string or managed identity.
- For AWS S3 in Spring, use AWS SDK v2 with S3Client.""",
    },
    # ==================================================================
    #  5. Error Handling (15 docs)
    # ==================================================================
    {
        "title": "On Error Propagate to Throw Exception",
        "category": "error-handling",
        "content": """MuleSoft on-error-propagate -> Spring Boot throw exception

MuleSoft XML:
```xml
<flow name="getOrderFlow">
    <http:listener config-ref="HTTP_Listener" path="/api/orders/{id}" method="GET"/>
    <db:select config-ref="Database_Config">
        <db:sql>SELECT * FROM orders WHERE id = :id</db:sql>
        <db:input-parameters><![CDATA[#[{id: attributes.uriParams.id}]]]></db:input-parameters>
    </db:select>
    <error-handler>
        <on-error-propagate type="DB:QUERY_EXECUTION">
            <set-payload value='{"error": "Database query failed"}'/>
            <set-variable variableName="httpStatus" value="500"/>
        </on-error-propagate>
    </error-handler>
</flow>
```

Spring Boot Java:
```java
@Service
public class OrderService {
    public OrderDTO findById(Long id) {
        try {
            return repository.findById(id)
                .map(this::toDTO)
                .orElseThrow(() -> new ResourceNotFoundException("Order", id));
        } catch (DataAccessException e) {
            throw new DatabaseException("Database query failed", e);
        }
    }
}

@ControllerAdvice
public class GlobalExceptionHandler {
    @ExceptionHandler(DatabaseException.class)
    public ResponseEntity<ErrorResponse> handleDbError(DatabaseException ex) {
        return ResponseEntity.status(500).body(new ErrorResponse(500, ex.getMessage()));
    }
}
```

Key mapping rules:
- on-error-propagate re-throws the error after handling; maps to throwing a new exception.
- The error type (DB:QUERY_EXECUTION) maps to catching specific exception classes.
- Error payload and httpStatus map to @ExceptionHandler returning ResponseEntity.
- Use @ControllerAdvice for centralized error handling across all controllers.""",
    },
    {
        "title": "On Error Continue to Try-Catch with Logging",
        "category": "error-handling",
        "content": """MuleSoft on-error-continue -> Spring Boot try-catch with logging

MuleSoft XML:
```xml
<flow name="enrichOrderFlow">
    <http:listener config-ref="HTTP_Listener" path="/api/orders/{id}/enrich" method="POST"/>
    <try>
        <http:request config-ref="External_API" path="/v1/customer/#[vars.customerId]" method="GET"/>
        <error-handler>
            <on-error-continue type="HTTP:CONNECTIVITY">
                <logger level="WARN" message="External API unavailable, continuing without enrichment"/>
                <set-variable variableName="customerData" value="#[null]"/>
            </on-error-continue>
        </error-handler>
    </try>
    <logger message="Continuing with order processing"/>
</flow>
```

Spring Boot Java:
```java
@Service
@Slf4j
public class OrderEnrichmentService {
    private final CustomerApiClient customerApiClient;

    public OrderDTO enrichOrder(Long orderId) {
        OrderDTO order = orderService.findById(orderId);
        try {
            CustomerDTO customer = customerApiClient.getCustomer(order.getCustomerId());
            order.setCustomerName(customer.getName());
        } catch (WebClientResponseException | WebClientRequestException e) {
            log.warn("External API unavailable, continuing without enrichment: {}", e.getMessage());
            // Continue processing without customer data
        }
        log.info("Continuing with order processing");
        return order;
    }
}
```

Key mapping rules:
- on-error-continue swallows the error and continues the flow; maps to try-catch that catches and logs.
- The flow continues after the catch block, same as MuleSoft behavior.
- Use specific exception types in the catch clause.
- on-error-continue with set-variable null maps to leaving the field unset or using a default.""",
    },
    {
        "title": "Global Error Handler to ControllerAdvice",
        "category": "error-handling",
        "content": """MuleSoft Global Error Handler -> Spring Boot @ControllerAdvice

MuleSoft XML:
```xml
<error-handler name="globalErrorHandler">
    <on-error-propagate type="HTTP:NOT_FOUND">
        <set-payload value='{"error": "Resource not found", "status": 404}'/>
        <set-variable variableName="httpStatus" value="404"/>
    </on-error-propagate>
    <on-error-propagate type="HTTP:UNAUTHORIZED">
        <set-payload value='{"error": "Unauthorized", "status": 401}'/>
        <set-variable variableName="httpStatus" value="401"/>
    </on-error-propagate>
    <on-error-propagate type="ANY">
        <set-payload value='{"error": "Internal server error", "status": 500}'/>
        <set-variable variableName="httpStatus" value="500"/>
    </on-error-propagate>
</error-handler>
```

Spring Boot Java:
```java
@ControllerAdvice
@Slf4j
public class GlobalExceptionHandler {

    @ExceptionHandler(ResourceNotFoundException.class)
    public ResponseEntity<ErrorResponse> handleNotFound(ResourceNotFoundException ex) {
        log.warn("Resource not found: {}", ex.getMessage());
        return ResponseEntity.status(HttpStatus.NOT_FOUND)
            .body(new ErrorResponse(404, "Resource not found", ex.getMessage()));
    }

    @ExceptionHandler(UnauthorizedException.class)
    public ResponseEntity<ErrorResponse> handleUnauthorized(UnauthorizedException ex) {
        log.warn("Unauthorized: {}", ex.getMessage());
        return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
            .body(new ErrorResponse(401, "Unauthorized", ex.getMessage()));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ErrorResponse> handleGeneral(Exception ex) {
        log.error("Internal server error", ex);
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
            .body(new ErrorResponse(500, "Internal server error", null));
    }
}

public record ErrorResponse(int status, String error, String message) {}
```

Key mapping rules:
- MuleSoft global error-handler maps to @ControllerAdvice class.
- Each on-error-propagate with type maps to @ExceptionHandler for that exception.
- type="ANY" maps to @ExceptionHandler(Exception.class) as a catch-all.
- Error payload maps to ErrorResponse DTO returned in ResponseEntity.""",
    },
    {
        "title": "Error Type HTTP NOT_FOUND to 404",
        "category": "error-handling",
        "content": """MuleSoft HTTP:NOT_FOUND -> Spring Boot 404 Not Found

MuleSoft XML:
```xml
<flow name="getCustomerFlow">
    <http:listener config-ref="HTTP_Listener" path="/api/customers/{id}" method="GET"/>
    <db:select config-ref="Database_Config">
        <db:sql>SELECT * FROM customers WHERE id = :id</db:sql>
        <db:input-parameters><![CDATA[#[{id: attributes.uriParams.id}]]]></db:input-parameters>
    </db:select>
    <choice>
        <when expression="#[sizeOf(payload) == 0]">
            <raise-error type="HTTP:NOT_FOUND" description="Customer not found"/>
        </when>
    </choice>
</flow>
```

Spring Boot Java:
```java
public class ResourceNotFoundException extends RuntimeException {
    public ResourceNotFoundException(String resource, Object id) {
        super(String.format("%s not found with id: %s", resource, id));
    }
}

@Service
public class CustomerService {
    public CustomerDTO findById(Long id) {
        return repository.findById(id)
            .map(this::toDTO)
            .orElseThrow(() -> new ResourceNotFoundException("Customer", id));
    }
}

@ExceptionHandler(ResourceNotFoundException.class)
@ResponseStatus(HttpStatus.NOT_FOUND)
public ErrorResponse handleNotFound(ResourceNotFoundException ex) {
    return new ErrorResponse(404, ex.getMessage());
}
```

Key mapping rules:
- MuleSoft raise-error HTTP:NOT_FOUND maps to throwing ResourceNotFoundException.
- Empty query result check maps to Optional.orElseThrow().
- @ExceptionHandler returns 404 status via @ResponseStatus or ResponseEntity.""",
    },
    {
        "title": "Error Type HTTP UNAUTHORIZED to 401",
        "category": "error-handling",
        "content": """MuleSoft HTTP:UNAUTHORIZED -> Spring Boot 401 Unauthorized

MuleSoft XML:
```xml
<flow name="securedFlow">
    <http:listener config-ref="HTTP_Listener" path="/api/secure" method="GET"/>
    <choice>
        <when expression="#[attributes.headers.Authorization == null]">
            <raise-error type="HTTP:UNAUTHORIZED" description="Missing authorization header"/>
        </when>
    </choice>
    <error-handler>
        <on-error-propagate type="HTTP:UNAUTHORIZED">
            <set-payload value='{"error": "Unauthorized", "message": "Valid credentials required"}'/>
            <set-variable variableName="httpStatus" value="401"/>
        </on-error-propagate>
    </error-handler>
</flow>
```

Spring Boot Java:
```java
public class UnauthorizedException extends RuntimeException {
    public UnauthorizedException(String message) { super(message); }
}

// In security filter or service:
if (authHeader == null || !authHeader.startsWith("Bearer ")) {
    throw new UnauthorizedException("Missing authorization header");
}

@ExceptionHandler(UnauthorizedException.class)
public ResponseEntity<ErrorResponse> handleUnauthorized(UnauthorizedException ex) {
    return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
        .body(new ErrorResponse(401, ex.getMessage()));
}
```

Key mapping rules:
- MuleSoft raise-error HTTP:UNAUTHORIZED maps to throwing UnauthorizedException.
- Authorization header check moves to a security filter or interceptor.
- In Spring Security, use AuthenticationEntryPoint for 401 responses.
- Always include WWW-Authenticate header in 401 responses per HTTP spec.""",
    },
    {
        "title": "Error Type HTTP BAD_REQUEST to 400",
        "category": "error-handling",
        "content": """MuleSoft HTTP:BAD_REQUEST -> Spring Boot 400 Bad Request

MuleSoft XML:
```xml
<flow name="createOrderFlow">
    <http:listener config-ref="HTTP_Listener" path="/api/orders" method="POST"/>
    <validation:is-not-null value="#[payload.customerId]" message="Customer ID required"/>
    <validation:is-true expression="#[payload.items != null and sizeOf(payload.items) > 0]" message="At least one item required"/>
    <error-handler>
        <on-error-propagate type="VALIDATION:INVALID">
            <set-payload value='{"error": "Bad Request", "message": "#[error.description]"}'/>
            <set-variable variableName="httpStatus" value="400"/>
        </on-error-propagate>
    </error-handler>
</flow>
```

Spring Boot Java:
```java
public class CreateOrderRequest {
    @NotNull(message = "Customer ID required")
    private Long customerId;

    @NotEmpty(message = "At least one item required")
    private List<OrderItemRequest> items;
}

@PostMapping("/orders")
public ResponseEntity<OrderDTO> createOrder(@Valid @RequestBody CreateOrderRequest request) {
    return ResponseEntity.status(HttpStatus.CREATED).body(orderService.create(request));
}

@ExceptionHandler(MethodArgumentNotValidException.class)
public ResponseEntity<ErrorResponse> handleValidation(MethodArgumentNotValidException ex) {
    List<String> errors = ex.getBindingResult().getFieldErrors().stream()
        .map(e -> e.getField() + ": " + e.getDefaultMessage())
        .collect(Collectors.toList());
    return ResponseEntity.badRequest()
        .body(new ErrorResponse(400, "Validation failed", errors));
}
```

Key mapping rules:
- MuleSoft VALIDATION:INVALID maps to MethodArgumentNotValidException.
- validation:is-not-null maps to @NotNull annotation.
- validation:is-true maps to @NotEmpty, @Size, or custom validator.
- Collect all field errors into a list for the error response.""",
    },
    {
        "title": "Error Type CONNECTIVITY to 503",
        "category": "error-handling",
        "content": """MuleSoft CONNECTIVITY Error -> Spring Boot 503 Service Unavailable

MuleSoft XML:
```xml
<flow name="callExternalFlow">
    <http:request config-ref="External_API" path="/v1/data" method="GET"/>
    <error-handler>
        <on-error-propagate type="HTTP:CONNECTIVITY">
            <set-payload value='{"error": "Service unavailable", "message": "External service is down"}'/>
            <set-variable variableName="httpStatus" value="503"/>
        </on-error-propagate>
        <on-error-propagate type="HTTP:TIMEOUT">
            <set-payload value='{"error": "Gateway timeout", "message": "External service timed out"}'/>
            <set-variable variableName="httpStatus" value="504"/>
        </on-error-propagate>
    </error-handler>
</flow>
```

Spring Boot Java:
```java
@Service
public class ExternalApiClient {
    public DataDTO fetchData() {
        try {
            return webClient.get().uri("/v1/data").retrieve()
                .bodyToMono(DataDTO.class).block();
        } catch (WebClientRequestException e) {
            throw new ServiceUnavailableException("External service is down", e);
        } catch (WebClientResponseException.GatewayTimeout e) {
            throw new GatewayTimeoutException("External service timed out", e);
        }
    }
}

@ExceptionHandler(ServiceUnavailableException.class)
public ResponseEntity<ErrorResponse> handleServiceUnavailable(ServiceUnavailableException ex) {
    return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE)
        .body(new ErrorResponse(503, ex.getMessage()));
}
```

Key mapping rules:
- MuleSoft HTTP:CONNECTIVITY maps to WebClientRequestException (connection refused, DNS failure).
- HTTP:TIMEOUT maps to WebClientResponseException.GatewayTimeout or ReadTimeoutException.
- Map to 503 Service Unavailable or 504 Gateway Timeout respectively.
- Add Retry-After header in 503 responses to hint when to retry.""",
    },
    {
        "title": "Custom Error Types to Custom Exceptions",
        "category": "error-handling",
        "content": """MuleSoft Custom Error Types -> Spring Boot Custom Exception Classes

MuleSoft XML:
```xml
<flow name="processPaymentFlow">
    <choice>
        <when expression="#[payload.amount > vars.accountBalance]">
            <raise-error type="APP:INSUFFICIENT_FUNDS" description="Insufficient funds for this transaction"/>
        </when>
        <when expression="#[payload.amount <= 0]">
            <raise-error type="APP:INVALID_AMOUNT" description="Amount must be positive"/>
        </when>
    </choice>
    <error-handler>
        <on-error-propagate type="APP:INSUFFICIENT_FUNDS">
            <set-payload value='{"error": "Insufficient funds"}'/>
            <set-variable variableName="httpStatus" value="422"/>
        </on-error-propagate>
        <on-error-propagate type="APP:INVALID_AMOUNT">
            <set-payload value='{"error": "Invalid amount"}'/>
            <set-variable variableName="httpStatus" value="400"/>
        </on-error-propagate>
    </error-handler>
</flow>
```

Spring Boot Java:
```java
public class InsufficientFundsException extends RuntimeException {
    public InsufficientFundsException(String message) { super(message); }
}

public class InvalidAmountException extends RuntimeException {
    public InvalidAmountException(String message) { super(message); }
}

@Service
public class PaymentService {
    public PaymentResult processPayment(PaymentRequest request) {
        if (request.getAmount().compareTo(BigDecimal.ZERO) <= 0) {
            throw new InvalidAmountException("Amount must be positive");
        }
        BigDecimal balance = accountService.getBalance(request.getAccountId());
        if (request.getAmount().compareTo(balance) > 0) {
            throw new InsufficientFundsException("Insufficient funds for this transaction");
        }
        return executePayment(request);
    }
}

@ExceptionHandler(InsufficientFundsException.class)
public ResponseEntity<ErrorResponse> handleInsufficientFunds(InsufficientFundsException ex) {
    return ResponseEntity.unprocessableEntity().body(new ErrorResponse(422, ex.getMessage()));
}
```

Key mapping rules:
- MuleSoft raise-error type="APP:X" maps to custom exception classes.
- Create one exception class per error type for clean separation.
- Each custom error type maps to a specific HTTP status code.
- Organize exceptions in a dedicated exceptions package.""",
    },
    {
        "title": "Error Response Format JSON Body",
        "category": "error-handling",
        "content": """MuleSoft Error Response JSON -> Spring Boot ErrorResponse DTO

MuleSoft XML:
```xml
<error-handler name="globalErrorHandler">
    <on-error-propagate>
        <ee:transform>
            <ee:set-payload><![CDATA[%dw 2.0
output application/json
---
{
    timestamp: now() as String {format: "yyyy-MM-dd'T'HH:mm:ss"},
    status: vars.httpStatus default 500,
    error: error.errorType.identifier,
    message: error.description,
    path: attributes.requestPath
}]]></ee:set-payload>
        </ee:transform>
    </on-error-propagate>
</error-handler>
```

Spring Boot Java:
```java
public class ErrorResponse {
    private final LocalDateTime timestamp;
    private final int status;
    private final String error;
    private final String message;
    private final String path;

    public ErrorResponse(int status, String error, String message, String path) {
        this.timestamp = LocalDateTime.now();
        this.status = status;
        this.error = error;
        this.message = message;
        this.path = path;
    }
}

@ControllerAdvice
public class GlobalExceptionHandler {
    @ExceptionHandler(ResourceNotFoundException.class)
    public ResponseEntity<ErrorResponse> handleNotFound(ResourceNotFoundException ex, HttpServletRequest req) {
        ErrorResponse error = new ErrorResponse(404, "Not Found", ex.getMessage(), req.getRequestURI());
        return ResponseEntity.status(HttpStatus.NOT_FOUND).body(error);
    }
}
```

Key mapping rules:
- MuleSoft error response payload maps to an ErrorResponse DTO class.
- Include timestamp, status, error type, message, and request path.
- Follow RFC 7807 Problem Details format for standard API error responses.
- Inject HttpServletRequest to access the request path in @ExceptionHandler.""",
    },
    {
        "title": "Retry Mechanism with Resilience4j",
        "category": "error-handling",
        "content": """MuleSoft until-successful -> Spring Boot @Retryable / Resilience4j

MuleSoft XML:
```xml
<flow name="reliableCallFlow">
    <until-successful maxRetries="3" millisBetweenRetries="2000">
        <http:request config-ref="External_API" path="/v1/process" method="POST">
            <http:body>#[payload]</http:body>
        </http:request>
    </until-successful>
</flow>
```

Spring Boot Java (Spring Retry):
```java
@Service
@Slf4j
public class ExternalApiService {

    @Retryable(maxAttempts = 3, backoff = @Backoff(delay = 2000),
        retryFor = {WebClientRequestException.class, WebClientResponseException.ServiceUnavailable.class})
    public ProcessResult process(ProcessRequest request) {
        log.info("Calling external API (attempt)");
        return webClient.post().uri("/v1/process")
            .bodyValue(request).retrieve()
            .bodyToMono(ProcessResult.class).block();
    }

    @Recover
    public ProcessResult recover(Exception ex, ProcessRequest request) {
        log.error("All retries exhausted for request: {}", request, ex);
        throw new ServiceUnavailableException("External service unavailable after retries");
    }
}
```

Key mapping rules:
- MuleSoft until-successful maps to @Retryable annotation.
- maxRetries maps to maxAttempts parameter.
- millisBetweenRetries maps to @Backoff(delay = ...).
- @Recover method handles the case when all retries are exhausted.
- Enable with @EnableRetry on a configuration class.""",
    },
    {
        "title": "Circuit Breaker with Resilience4j",
        "category": "error-handling",
        "content": """MuleSoft Pattern: Circuit Breaker -> Resilience4j CircuitBreaker

MuleSoft does not have a built-in circuit breaker; it relies on until-successful or custom logic.

Spring Boot Java (Resilience4j):
```java
@Service
@Slf4j
public class PaymentGatewayService {

    @CircuitBreaker(name = "paymentGateway", fallbackMethod = "paymentFallback")
    public PaymentResult processPayment(PaymentRequest request) {
        return webClient.post().uri("/v1/payments")
            .bodyValue(request).retrieve()
            .bodyToMono(PaymentResult.class).block();
    }

    private PaymentResult paymentFallback(PaymentRequest request, Throwable t) {
        log.warn("Circuit breaker open for payment gateway: {}", t.getMessage());
        return new PaymentResult("PENDING", "Payment queued for retry");
    }
}
```

application.yml:
```yaml
resilience4j:
  circuitbreaker:
    instances:
      paymentGateway:
        slidingWindowSize: 10
        failureRateThreshold: 50
        waitDurationInOpenState: 30s
        permittedNumberOfCallsInHalfOpenState: 3
        slowCallDurationThreshold: 5s
```

MuleSoft equivalent pattern (manual):
```xml
<flow name="circuitBreakerFlow">
    <os:retrieve key="circuitState" target="state" objectStore="circuitStore"/>
    <choice>
        <when expression="#[vars.state == 'OPEN']">
            <raise-error type="APP:CIRCUIT_OPEN" description="Circuit breaker is open"/>
        </when>
        <otherwise>
            <until-successful maxRetries="1">
                <http:request config-ref="Payment_API" path="/v1/payments" method="POST"/>
            </until-successful>
        </otherwise>
    </choice>
</flow>
```

Key mapping rules:
- MuleSoft has no native circuit breaker; Resilience4j provides this in Spring Boot.
- @CircuitBreaker annotation wraps the method with circuit breaker logic.
- Configure sliding window, failure threshold, and wait duration in YAML.
- Fallback method provides degraded service when the circuit is open.""",
    },
    {
        "title": "Dead Letter Queue with Spring AMQP",
        "category": "error-handling",
        "content": """MuleSoft Error Queue -> Spring AMQP Dead Letter Queue

MuleSoft XML:
```xml
<flow name="processMessageFlow">
    <jms:listener config-ref="JMS_Config" destination="order.queue"/>
    <error-handler>
        <on-error-propagate>
            <jms:publish config-ref="JMS_Config" destination="order.queue.dlq">
                <jms:body>#[output application/json --- {originalPayload: payload, error: error.description}]</jms:body>
            </jms:publish>
        </on-error-propagate>
    </error-handler>
</flow>
```

Spring Boot Java:
```java
@Configuration
public class RabbitDLQConfig {
    @Bean
    public Queue orderQueue() {
        return QueueBuilder.durable("order.queue")
            .withArgument("x-dead-letter-exchange", "")
            .withArgument("x-dead-letter-routing-key", "order.queue.dlq")
            .build();
    }

    @Bean
    public Queue deadLetterQueue() {
        return QueueBuilder.durable("order.queue.dlq").build();
    }
}

@Component
@Slf4j
public class OrderConsumer {
    @RabbitListener(queues = "order.queue")
    public void process(OrderMessage message) {
        try {
            orderService.process(message);
        } catch (Exception e) {
            log.error("Processing failed, sending to DLQ", e);
            throw new AmqpRejectAndDontRequeueException("Processing failed", e);
        }
    }

    @RabbitListener(queues = "order.queue.dlq")
    public void processDLQ(OrderMessage message) {
        log.warn("DLQ message: {}", message);
        // Alert, log, or attempt recovery
    }
}
```

Key mapping rules:
- MuleSoft error handler publishing to DLQ maps to RabbitMQ dead letter exchange.
- Throwing AmqpRejectAndDontRequeueException sends to DLQ automatically.
- Configure DLQ via x-dead-letter-exchange and x-dead-letter-routing-key.
- Create a separate @RabbitListener for DLQ processing.""",
    },
    {
        "title": "Compensation and Rollback with @Transactional",
        "category": "error-handling",
        "content": """MuleSoft Compensation / Rollback -> Spring Boot @Transactional Rollback

MuleSoft XML:
```xml
<flow name="orderSagaFlow">
    <try transactionalAction="ALWAYS_BEGIN">
        <flow-ref name="reserveInventory"/>
        <flow-ref name="chargePayment"/>
        <flow-ref name="createShipment"/>
        <error-handler>
            <on-error-propagate>
                <flow-ref name="releaseInventory"/>
                <flow-ref name="refundPayment"/>
                <logger level="ERROR" message="Order saga failed, compensating"/>
            </on-error-propagate>
        </error-handler>
    </try>
</flow>
```

Spring Boot Java:
```java
@Service
@Slf4j
public class OrderSagaService {

    @Transactional(rollbackFor = Exception.class)
    public OrderResult processOrder(CreateOrderRequest request) {
        try {
            inventoryService.reserve(request.getItems());
            paymentService.charge(request.getPayment());
            shipmentService.create(request.getShipping());
            return new OrderResult("SUCCESS");
        } catch (Exception e) {
            log.error("Order saga failed, compensating", e);
            compensate(request);
            throw e; // triggers @Transactional rollback
        }
    }

    private void compensate(CreateOrderRequest request) {
        try { inventoryService.release(request.getItems()); } catch (Exception ex) { log.error("Inventory release failed", ex); }
        try { paymentService.refund(request.getPayment()); } catch (Exception ex) { log.error("Payment refund failed", ex); }
    }
}
```

Key mapping rules:
- MuleSoft try with transaction maps to @Transactional for DB rollback.
- on-error-propagate with compensation maps to explicit compensate() calls.
- For distributed transactions (saga pattern), implement manual compensation.
- DB operations roll back automatically; external API calls need explicit undo.""",
    },
    {
        "title": "Validation Errors with Bean Validation",
        "category": "error-handling",
        "content": """MuleSoft Validation Module -> Spring Boot @Valid + BindingResult

MuleSoft XML:
```xml
<flow name="createAccountFlow">
    <http:listener config-ref="HTTP_Listener" path="/api/accounts" method="POST"/>
    <validation:is-not-null value="#[payload.email]" message="Email is required"/>
    <validation:matches-regex value="#[payload.email]" regex="^[\\w.]+@[\\w.]+$" message="Invalid email format"/>
    <validation:is-not-blank value="#[payload.name]" message="Name cannot be blank"/>
    <validation:validate-size value="#[payload.password]" min="8" max="128" message="Password must be 8-128 chars"/>
</flow>
```

Spring Boot Java:
```java
public class CreateAccountRequest {
    @NotNull(message = "Email is required")
    @Email(message = "Invalid email format")
    private String email;

    @NotBlank(message = "Name cannot be blank")
    private String name;

    @Size(min = 8, max = 128, message = "Password must be 8-128 chars")
    private String password;
}

@PostMapping("/accounts")
public ResponseEntity<?> createAccount(@Valid @RequestBody CreateAccountRequest request) {
    AccountDTO account = accountService.create(request);
    return ResponseEntity.status(HttpStatus.CREATED).body(account);
}
```

Key mapping rules:
- MuleSoft validation:is-not-null maps to @NotNull.
- validation:matches-regex maps to @Pattern(regexp = "...") or @Email.
- validation:is-not-blank maps to @NotBlank.
- validation:validate-size maps to @Size(min, max).
- @Valid triggers all validations; errors auto-throw MethodArgumentNotValidException.""",
    },
    {
        "title": "Async Error Handling with CompletableFuture",
        "category": "error-handling",
        "content": """MuleSoft Async Error Handling -> Spring Boot CompletableFuture.exceptionally

MuleSoft XML:
```xml
<flow name="asyncProcessFlow">
    <async>
        <http:request config-ref="External_API" path="/v1/notify" method="POST"/>
        <error-handler>
            <on-error-continue>
                <logger level="ERROR" message="Async notification failed: #[error.description]"/>
            </on-error-continue>
        </error-handler>
    </async>
</flow>
```

Spring Boot Java:
```java
@Service
@Slf4j
public class NotificationService {

    @Async
    public CompletableFuture<Void> notifyAsync(NotificationRequest request) {
        return CompletableFuture.runAsync(() -> {
            webClient.post().uri("/v1/notify")
                .bodyValue(request).retrieve()
                .bodyToMono(Void.class).block();
        }).exceptionally(ex -> {
            log.error("Async notification failed: {}", ex.getMessage());
            return null;
        });
    }
}

@Configuration
@EnableAsync
public class AsyncConfig {
    @Bean
    public Executor taskExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(5);
        executor.setMaxPoolSize(10);
        executor.setQueueCapacity(25);
        executor.setThreadNamePrefix("async-");
        executor.initialize();
        return executor;
    }
}
```

Key mapping rules:
- MuleSoft async scope maps to @Async annotation or CompletableFuture.runAsync().
- on-error-continue in async maps to .exceptionally() handler.
- Configure thread pool with ThreadPoolTaskExecutor.
- Enable with @EnableAsync on a configuration class.
- Async errors do not propagate to the caller.""",
    },
    # ==================================================================
    #  6. Spring Boot Best Practices (25 docs)
    # ==================================================================
    {
        "title": "Spring Boot Project Structure",
        "category": "springboot",
        "content": """MuleSoft Project -> Spring Boot Project Structure

MuleSoft structure:
```
src/main/mule/
  global-config.xml
  api-flows.xml
  business-flows.xml
src/main/resources/
  config.properties
```

Spring Boot recommended structure:
```
src/main/java/com/example/app/
  config/          # @Configuration classes
  controller/      # @RestController classes
  service/         # @Service business logic
  repository/      # JPA repositories
  domain/          # @Entity classes
  dto/             # Request/Response DTOs
  exception/       # Custom exception classes
  mapper/          # DTO-Entity mappers
  client/          # External API clients
  filter/          # Servlet filters
  util/            # Utility classes
src/main/resources/
  application.yml
  application-dev.yml
  application-prod.yml
  db/migration/    # Flyway migrations
```

MuleSoft XML config equivalent:
```xml
<!-- MuleSoft uses XML files to organize flows -->
<flow name="orderFlow">
    <!-- All logic in one file -->
</flow>
```

Spring Boot Java:
```java
// Logic is separated across layers
@RestController      // Controller layer
@Service             // Service layer
@Repository          // Data access layer
@Configuration       // Configuration layer
```

Key mapping rules:
- MuleSoft XML flow files map to controller + service + repository layers.
- Global configs map to @Configuration classes.
- Properties files map to application.yml with profiles.
- Each MuleSoft flow typically maps to a controller method calling a service.""",
    },
    {
        "title": "Constructor Injection Best Practice",
        "category": "springboot",
        "content": """MuleSoft Config References -> Spring Boot Constructor Injection

MuleSoft XML:
```xml
<flow name="orderFlow">
    <http:listener config-ref="HTTP_Listener" path="/api/orders" method="GET"/>
    <flow-ref name="orderSubflow"/>
</flow>
<sub-flow name="orderSubflow">
    <db:select config-ref="Database_Config">
        <db:sql>SELECT * FROM orders</db:sql>
    </db:select>
</sub-flow>
```

Spring Boot Java (GOOD - constructor injection):
```java
@Service
public class OrderService {
    private final OrderRepository orderRepository;
    private final PaymentService paymentService;
    private final NotificationService notificationService;

    // Single constructor - @Autowired not needed
    public OrderService(OrderRepository orderRepository,
                        PaymentService paymentService,
                        NotificationService notificationService) {
        this.orderRepository = orderRepository;
        this.paymentService = paymentService;
        this.notificationService = notificationService;
    }
}
```

Spring Boot Java (BAD - field injection):
```java
@Service
public class OrderService {
    @Autowired private OrderRepository orderRepository;  // BAD: untestable
    @Autowired private PaymentService paymentService;     // BAD: hidden deps
}
```

Key mapping rules:
- MuleSoft config-ref dependencies map to constructor-injected Spring beans.
- Always use constructor injection over @Autowired field injection.
- Constructor injection makes dependencies explicit and testable.
- With a single constructor, @Autowired annotation is optional.
- Use Lombok @RequiredArgsConstructor to reduce boilerplate.""",
    },
    {
        "title": "DTO Pattern for Request Response",
        "category": "springboot",
        "content": """MuleSoft Payload Transformation -> Spring Boot DTO Pattern

MuleSoft XML:
```xml
<ee:transform>
    <ee:set-payload><![CDATA[%dw 2.0
output application/json
---
{
    id: payload.id,
    fullName: payload.first_name ++ " " ++ payload.last_name,
    email: payload.email
}]]></ee:set-payload>
</ee:transform>
```

Spring Boot Java:
```java
// Request DTO
public class CreateCustomerRequest {
    @NotBlank private String firstName;
    @NotBlank private String lastName;
    @Email private String email;
    // getters, setters
}

// Response DTO
public class CustomerResponse {
    private Long id;
    private String fullName;
    private String email;
    // getters, setters

    public static CustomerResponse from(Customer entity) {
        CustomerResponse dto = new CustomerResponse();
        dto.setId(entity.getId());
        dto.setFullName(entity.getFirstName() + " " + entity.getLastName());
        dto.setEmail(entity.getEmail());
        return dto;
    }
}

// Or use Java Records (Java 16+):
public record CustomerResponse(Long id, String fullName, String email) {
    public static CustomerResponse from(Customer entity) {
        return new CustomerResponse(entity.getId(),
            entity.getFirstName() + " " + entity.getLastName(),
            entity.getEmail());
    }
}
```

Key mapping rules:
- MuleSoft DataWeave transform maps to DTO classes with static factory methods.
- Separate request DTOs (with validation) from response DTOs.
- Never expose JPA entities directly in API responses.
- Use Java Records for immutable response DTOs.
- DTOs decouple API contract from internal data model.""",
    },
    {
        "title": "Mapper Pattern with MapStruct",
        "category": "springboot",
        "content": """MuleSoft DataWeave Mapping -> Spring Boot MapStruct / Manual Mapper

MuleSoft XML:
```xml
<ee:transform>
    <ee:set-payload><![CDATA[%dw 2.0
output application/java
---
payload map {
    id: $.id,
    name: $.first_name ++ " " ++ $.last_name,
    emailAddress: $.email,
    active: $.status == "ACTIVE"
}]]></ee:set-payload>
</ee:transform>
```

Spring Boot Java (MapStruct):
```java
@Mapper(componentModel = "spring")
public interface CustomerMapper {
    @Mapping(target = "name", expression = "java(entity.getFirstName() + \" \" + entity.getLastName())")
    @Mapping(source = "email", target = "emailAddress")
    @Mapping(target = "active", expression = "java(\"ACTIVE\".equals(entity.getStatus()))")
    CustomerDTO toDTO(Customer entity);

    List<CustomerDTO> toDTOList(List<Customer> entities);
}
```

Spring Boot Java (Manual Mapper):
```java
@Component
public class CustomerMapper {
    public CustomerDTO toDTO(Customer entity) {
        CustomerDTO dto = new CustomerDTO();
        dto.setId(entity.getId());
        dto.setName(entity.getFirstName() + " " + entity.getLastName());
        dto.setEmailAddress(entity.getEmail());
        dto.setActive("ACTIVE".equals(entity.getStatus()));
        return dto;
    }

    public List<CustomerDTO> toDTOList(List<Customer> entities) {
        return entities.stream().map(this::toDTO).collect(Collectors.toList());
    }
}
```

Key mapping rules:
- DataWeave map transformations map to MapStruct @Mapper or manual mapper classes.
- MapStruct generates mapping code at compile time (zero runtime overhead).
- Use @Mapping for field name differences and expression for computed fields.
- Keep mappers as separate @Component classes for testability.""",
    },
    {
        "title": "Repository Pattern with JPA",
        "category": "springboot",
        "content": """MuleSoft DB Operations -> Spring Boot JPA Repository Pattern

MuleSoft XML:
```xml
<flow name="customerOperations">
    <db:select config-ref="Database_Config">
        <db:sql>SELECT * FROM customers WHERE status = :status ORDER BY name</db:sql>
    </db:select>
    <db:insert config-ref="Database_Config">
        <db:sql>INSERT INTO customers (name, email, status) VALUES (:name, :email, :status)</db:sql>
    </db:insert>
</flow>
```

Spring Boot Java:
```java
public interface CustomerRepository extends JpaRepository<Customer, Long> {
    List<Customer> findByStatusOrderByName(String status);
    Optional<Customer> findByEmail(String email);
    boolean existsByEmail(String email);

    @Query("SELECT c FROM Customer c WHERE c.status = :status AND c.createdAt > :since")
    Page<Customer> findActiveCustomersSince(@Param("status") String status,
                                              @Param("since") LocalDateTime since,
                                              Pageable pageable);

    @Modifying
    @Query("UPDATE Customer c SET c.status = :status WHERE c.lastLoginAt < :cutoff")
    int deactivateInactiveCustomers(@Param("status") String status, @Param("cutoff") LocalDateTime cutoff);
}
```

Key mapping rules:
- MuleSoft db:select maps to repository derived query methods or @Query.
- db:insert maps to repository.save(entity).
- WHERE clauses map to findByXxxAndYyy naming convention.
- ORDER BY maps to OrderBy suffix in method name.
- Complex queries use @Query with JPQL.
- Extend JpaRepository for full CRUD + pagination support.""",
    },
    {
        "title": "Service Layer Pattern",
        "category": "springboot",
        "content": """MuleSoft Flow Logic -> Spring Boot Service Layer

MuleSoft XML:
```xml
<flow name="createOrderFlow">
    <http:listener config-ref="HTTP_Listener" path="/api/orders" method="POST"/>
    <ee:transform><!-- validate and transform --></ee:transform>
    <db:insert config-ref="Database_Config"><!-- insert order --></db:insert>
    <flow-ref name="updateInventorySubflow"/>
    <flow-ref name="sendNotificationSubflow"/>
    <ee:transform><!-- build response --></ee:transform>
</flow>
```

Spring Boot Java:
```java
@Service
@Slf4j
@Transactional
public class OrderService {
    private final OrderRepository orderRepository;
    private final InventoryService inventoryService;
    private final NotificationService notificationService;
    private final OrderMapper mapper;

    public OrderService(OrderRepository orderRepository, InventoryService inventoryService,
                         NotificationService notificationService, OrderMapper mapper) {
        this.orderRepository = orderRepository;
        this.inventoryService = inventoryService;
        this.notificationService = notificationService;
        this.mapper = mapper;
    }

    public OrderDTO createOrder(CreateOrderRequest request) {
        log.info("Creating order for customer {}", request.getCustomerId());

        // Validate
        validateOrderRequest(request);

        // Create order entity
        Order order = mapper.toEntity(request);
        order.setStatus("PENDING");
        Order saved = orderRepository.save(order);

        // Update inventory
        inventoryService.reserve(request.getItems());

        // Send notification (async)
        notificationService.sendOrderConfirmation(saved);

        return mapper.toDTO(saved);
    }

    private void validateOrderRequest(CreateOrderRequest request) {
        if (request.getItems().isEmpty()) {
            throw new BadRequestException("Order must have at least one item");
        }
    }
}
```

Key mapping rules:
- MuleSoft flow logic maps to @Service methods.
- Flow-ref to sub-flows maps to calling other service methods.
- Transform steps map to mapper calls.
- DB operations map to repository calls.
- Service layer orchestrates business logic and transaction management.""",
    },
    {
        "title": "Configuration Properties",
        "category": "springboot",
        "content": """MuleSoft Properties -> Spring Boot @ConfigurationProperties

MuleSoft XML:
```xml
<configuration-properties file="config.properties"/>
<!-- config.properties: api.timeout=5000, api.maxRetries=3, api.baseUrl=https://api.example.com -->
<http:request-config name="API_Config" responseTimeout="${api.timeout}">
    <http:request-connection host="${api.baseUrl}" port="443"/>
</http:request-config>
```

Spring Boot Java:
```java
@ConfigurationProperties(prefix = "api")
@Validated
public class ApiProperties {
    @NotBlank private String baseUrl;
    @Min(1000) private int timeout = 5000;
    @Min(1) private int maxRetries = 3;
    private Map<String, String> headers = new HashMap<>();
    // getters and setters
}

@Configuration
@EnableConfigurationProperties(ApiProperties.class)
public class ApiConfig {
    @Bean
    public WebClient apiWebClient(ApiProperties props) {
        HttpClient httpClient = HttpClient.create()
            .responseTimeout(Duration.ofMillis(props.getTimeout()));
        return WebClient.builder()
            .baseUrl(props.getBaseUrl())
            .clientConnector(new ReactorClientHttpConnector(httpClient))
            .build();
    }
}
```

application.yml:
```yaml
api:
  base-url: https://api.example.com
  timeout: 5000
  max-retries: 3
  headers:
    X-Api-Key: ${API_KEY}
```

Key mapping rules:
- MuleSoft ${property} references map to @ConfigurationProperties classes.
- Type-safe config binding with validation (@Validated, @NotBlank, @Min).
- Properties are grouped by prefix for clean organization.
- Use kebab-case in YAML (max-retries) mapping to camelCase (maxRetries).""",
    },
    {
        "title": "Profile-Based Configuration",
        "category": "springboot",
        "content": """MuleSoft Environment Properties -> Spring Boot Profiles

MuleSoft XML:
```xml
<configuration-properties file="${mule.env}.properties"/>
<!-- dev.properties, staging.properties, prod.properties -->
```

Spring Boot structure:
```
application.yml           # Shared config
application-dev.yml       # Development overrides
application-staging.yml   # Staging overrides
application-prod.yml      # Production overrides
```

Spring Boot Java:
```java
@Configuration
@Profile("dev")
public class DevConfig {
    @Bean
    public WebClient mockExternalApi() {
        return WebClient.builder().baseUrl("http://localhost:8089").build();
    }
}

@Configuration
@Profile("prod")
public class ProdConfig {
    @Bean
    public WebClient externalApi() {
        return WebClient.builder().baseUrl("https://api.example.com").build();
    }
}
```

Activation:
```bash
SPRING_PROFILES_ACTIVE=prod java -jar app.jar
```

Key mapping rules:
- MuleSoft ${mule.env} maps to SPRING_PROFILES_ACTIVE environment variable.
- Per-environment property files map to application-{profile}.yml files.
- @Profile annotation enables beans conditionally per environment.
- Profile-specific YAML overrides shared application.yml values.""",
    },
    {
        "title": "application.yml Best Practices",
        "category": "springboot",
        "content": """MuleSoft config.properties -> Spring Boot application.yml

MuleSoft properties:
```xml
<configuration-properties file="config.properties"/>
<!-- db.host=localhost, db.port=5432, api.key=secret -->
```

Spring Boot application.yml best practices:
```yaml
server:
  port: ${PORT:8080}
  servlet:
    context-path: /api

spring:
  application:
    name: order-service
  datasource:
    url: jdbc:postgresql://${DB_HOST:localhost}:${DB_PORT:5432}/${DB_NAME:appdb}
    username: ${DB_USER:app}
    password: ${DB_PASSWORD:}
    hikari:
      maximum-pool-size: ${DB_POOL_SIZE:10}
  jpa:
    hibernate:
      ddl-auto: validate
    show-sql: false
  jackson:
    serialization:
      write-dates-as-timestamps: false
    default-property-inclusion: non_null

management:
  endpoints:
    web:
      exposure:
        include: health,info,metrics
  endpoint:
    health:
      show-details: when-authorized

logging:
  level:
    root: INFO
    com.example: ${LOG_LEVEL:INFO}
    org.hibernate.SQL: WARN
```

Key mapping rules:
- MuleSoft ${property} maps to ${ENV_VAR:default} in YAML.
- Use environment variables for all secrets and environment-specific values.
- Set sensible defaults for local development.
- Never commit secrets; use ${PASSWORD:} with empty default.
- Group related properties logically (spring.datasource, spring.jpa, etc.).""",
    },
    {
        "title": "Logging with SLF4J",
        "category": "springboot",
        "content": """MuleSoft Logger -> Spring Boot SLF4J @Slf4j

MuleSoft XML:
```xml
<flow name="orderFlow">
    <logger level="INFO" message="Processing order #[payload.orderId] for customer #[payload.customerId]"/>
    <logger level="DEBUG" message="Order details: #[payload]"/>
    <logger level="ERROR" message="Order failed: #[error.description]"/>
</flow>
```

Spring Boot Java:
```java
@Service
@Slf4j  // Lombok annotation - creates private static final Logger log
public class OrderService {

    public OrderDTO processOrder(OrderRequest request) {
        log.info("Processing order {} for customer {}", request.getOrderId(), request.getCustomerId());
        log.debug("Order details: {}", request);

        try {
            return doProcess(request);
        } catch (Exception e) {
            log.error("Order failed: {}", e.getMessage(), e);
            throw e;
        }
    }
}
```

application.yml:
```yaml
logging:
  level:
    root: INFO
    com.example.service: DEBUG
  pattern:
    console: "%d{yyyy-MM-dd HH:mm:ss} [%thread] %-5level %logger{36} - %msg%n"
  file:
    name: logs/application.log
```

Key mapping rules:
- MuleSoft logger with level maps to log.info/debug/warn/error.
- MEL expressions (#[payload]) map to {} placeholders in SLF4J.
- Use @Slf4j from Lombok to avoid boilerplate Logger declaration.
- Configure log levels per package in application.yml.
- Always use parameterized logging ({}) instead of string concatenation.""",
    },
    {
        "title": "Health Checks with Actuator",
        "category": "springboot",
        "content": """MuleSoft Health Check -> Spring Boot Actuator

MuleSoft XML (custom health endpoint):
```xml
<flow name="healthCheckFlow">
    <http:listener config-ref="HTTP_Listener" path="/health" method="GET"/>
    <try>
        <db:select config-ref="Database_Config">
            <db:sql>SELECT 1</db:sql>
        </db:select>
        <set-payload value='{"status": "UP", "database": "UP"}'/>
        <error-handler>
            <on-error-continue>
                <set-payload value='{"status": "DOWN", "database": "DOWN"}'/>
            </on-error-continue>
        </error-handler>
    </try>
</flow>
```

Spring Boot Java:
```java
// Actuator auto-provides /actuator/health
// Add custom health indicators:
@Component
public class ExternalApiHealthIndicator implements HealthIndicator {
    private final WebClient webClient;

    @Override
    public Health health() {
        try {
            webClient.get().uri("/health").retrieve()
                .bodyToMono(String.class).block(Duration.ofSeconds(3));
            return Health.up().withDetail("externalApi", "reachable").build();
        } catch (Exception e) {
            return Health.down().withDetail("externalApi", e.getMessage()).build();
        }
    }
}
```

pom.xml:
```xml
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-actuator</artifactId>
</dependency>
```

Key mapping rules:
- MuleSoft custom health flow maps to Spring Boot Actuator auto-configured endpoints.
- Database health is auto-detected; no manual SELECT 1 needed.
- Custom health indicators implement HealthIndicator interface.
- Actuator provides /actuator/health, /actuator/info, /actuator/metrics out of the box.""",
    },
    {
        "title": "API Versioning Strategies",
        "category": "springboot",
        "content": """MuleSoft API Versioning -> Spring Boot Versioning Strategies

MuleSoft XML:
```xml
<http:listener config-ref="HTTP_Listener" path="/api/v1/orders" method="GET"/>
<http:listener config-ref="HTTP_Listener" path="/api/v2/orders" method="GET"/>
```

Spring Boot Java (URL versioning - recommended):
```java
@RestController
@RequestMapping("/api/v1/orders")
public class OrderControllerV1 {
    @GetMapping
    public ResponseEntity<List<OrderV1DTO>> getOrders() { return ResponseEntity.ok(service.findAllV1()); }
}

@RestController
@RequestMapping("/api/v2/orders")
public class OrderControllerV2 {
    @GetMapping
    public ResponseEntity<List<OrderV2DTO>> getOrders() { return ResponseEntity.ok(service.findAllV2()); }
}
```

Spring Boot Java (Header versioning):
```java
@RestController
@RequestMapping("/api/orders")
public class OrderController {
    @GetMapping(headers = "X-API-Version=1")
    public ResponseEntity<List<OrderV1DTO>> getOrdersV1() { return ResponseEntity.ok(service.findAllV1()); }

    @GetMapping(headers = "X-API-Version=2")
    public ResponseEntity<List<OrderV2DTO>> getOrdersV2() { return ResponseEntity.ok(service.findAllV2()); }
}
```

Key mapping rules:
- MuleSoft path-based versioning maps directly to Spring @RequestMapping paths.
- URL versioning (/v1/, /v2/) is most explicit and cache-friendly.
- Header versioning uses headers attribute in @GetMapping.
- Keep old versions working while migrating consumers to new versions.""",
    },
    {
        "title": "Pagination and Sorting",
        "category": "springboot",
        "content": """MuleSoft Manual Pagination -> Spring Boot Pageable

MuleSoft XML:
```xml
<flow name="pagedQuery">
    <db:select config-ref="Database_Config">
        <db:sql>SELECT * FROM products ORDER BY #[vars.sortField] LIMIT :limit OFFSET :offset</db:sql>
        <db:input-parameters><![CDATA[#[{limit: vars.pageSize, offset: vars.page * vars.pageSize}]]]></db:input-parameters>
    </db:select>
</flow>
```

Spring Boot Java:
```java
@GetMapping("/products")
public ResponseEntity<Page<ProductDTO>> getProducts(
        @RequestParam(defaultValue = "0") int page,
        @RequestParam(defaultValue = "20") int size,
        @RequestParam(defaultValue = "name,asc") String[] sort) {
    List<Sort.Order> orders = new ArrayList<>();
    for (String s : sort) {
        String[] parts = s.split(",");
        orders.add(new Sort.Order(
            parts.length > 1 && parts[1].equalsIgnoreCase("desc") ? Sort.Direction.DESC : Sort.Direction.ASC,
            parts[0]));
    }
    Pageable pageable = PageRequest.of(page, size, Sort.by(orders));
    Page<ProductDTO> products = productService.findAll(pageable);
    return ResponseEntity.ok(products);
}
```

Response format:
```json
{
  "content": [...],
  "totalElements": 150,
  "totalPages": 8,
  "size": 20,
  "number": 0,
  "first": true,
  "last": false
}
```

Key mapping rules:
- MuleSoft manual LIMIT/OFFSET maps to Spring Data Pageable.
- Sort field and direction map to Sort.Order objects.
- Spring Data auto-generates pagination SQL from Pageable.
- Page response includes metadata (total elements, pages, etc.).""",
    },
    {
        "title": "OpenAPI Swagger Documentation",
        "category": "springboot",
        "content": """MuleSoft RAML/OAS API Spec -> Spring Boot OpenAPI/Swagger

MuleSoft RAML:
```yaml
#%RAML 1.0
title: Order API
/orders:
  get:
    description: Get all orders
    queryParameters:
      status: string
    responses:
      200:
        body: Order[]
```

Spring Boot Java (springdoc-openapi):
```java
@RestController
@RequestMapping("/api/orders")
@Tag(name = "Orders", description = "Order management endpoints")
public class OrderController {

    @Operation(summary = "Get all orders", description = "Returns paginated list of orders")
    @ApiResponses({
        @ApiResponse(responseCode = "200", description = "Orders retrieved"),
        @ApiResponse(responseCode = "400", description = "Invalid parameters")
    })
    @GetMapping
    public ResponseEntity<Page<OrderDTO>> getOrders(
            @Parameter(description = "Filter by status") @RequestParam(required = false) String status,
            Pageable pageable) {
        return ResponseEntity.ok(orderService.findAll(status, pageable));
    }
}
```

pom.xml:
```xml
<dependency>
    <groupId>org.springdoc</groupId>
    <artifactId>springdoc-openapi-starter-webmvc-ui</artifactId>
    <version>2.3.0</version>
</dependency>
```

Key mapping rules:
- MuleSoft RAML/OAS spec maps to springdoc-openapi annotations.
- API documentation auto-generated at /swagger-ui.html.
- @Tag, @Operation, @ApiResponse, @Parameter for metadata.
- OpenAPI JSON available at /v3/api-docs.""",
    },
    {
        "title": "Request Validation with Bean Validation",
        "category": "springboot",
        "content": """MuleSoft Validation Module -> Spring Boot @Valid + Constraints

MuleSoft XML:
```xml
<validation:is-not-null value="#[payload.name]"/>
<validation:validate-size value="#[payload.name]" min="2" max="100"/>
<validation:matches-regex value="#[payload.email]" regex="^[\\w.]+@[\\w.]+$"/>
<validation:is-true expression="#[payload.quantity > 0]"/>
```

Spring Boot Java:
```java
public class CreateOrderRequest {
    @NotNull(message = "Name is required")
    @Size(min = 2, max = 100, message = "Name must be 2-100 characters")
    private String name;

    @NotBlank @Email(message = "Valid email required")
    private String email;

    @Positive(message = "Quantity must be positive")
    private Integer quantity;

    @NotEmpty(message = "At least one item required")
    @Valid // Cascading validation
    private List<OrderItemRequest> items;

    @DecimalMin(value = "0.01", message = "Amount must be > 0")
    private BigDecimal amount;

    @Pattern(regexp = "^[A-Z]{3}$", message = "Currency must be 3 uppercase letters")
    private String currency;

    @Past(message = "Birth date must be in the past")
    private LocalDate birthDate;
}
```

Key mapping rules:
- validation:is-not-null maps to @NotNull.
- validate-size maps to @Size(min, max).
- matches-regex maps to @Pattern(regexp).
- is-true with expression maps to @Positive, @Min, @Max, or custom validator.
- @Valid on nested objects enables cascading validation.""",
    },
    {
        "title": "Response Wrapping with ResponseEntity",
        "category": "springboot",
        "content": """MuleSoft Set Payload + HTTP Status -> Spring Boot ResponseEntity

MuleSoft XML:
```xml
<flow name="createOrderFlow">
    <set-payload value='{"id": 123, "status": "created"}'/>
    <set-variable variableName="httpStatus" value="201"/>
    <set-variable variableName="location" value="/api/orders/123"/>
</flow>
```

Spring Boot Java:
```java
@PostMapping("/orders")
public ResponseEntity<OrderDTO> createOrder(@Valid @RequestBody CreateOrderRequest request) {
    OrderDTO order = orderService.create(request);
    URI location = ServletUriComponentsBuilder.fromCurrentRequest()
        .path("/{id}").buildAndExpand(order.getId()).toUri();
    return ResponseEntity
        .created(location)          // 201 with Location header
        .body(order);
}

@GetMapping("/orders/{id}")
public ResponseEntity<OrderDTO> getOrder(@PathVariable Long id) {
    return orderService.findById(id)
        .map(ResponseEntity::ok)    // 200
        .orElse(ResponseEntity.notFound().build());  // 404
}

@DeleteMapping("/orders/{id}")
public ResponseEntity<Void> deleteOrder(@PathVariable Long id) {
    orderService.delete(id);
    return ResponseEntity.noContent().build();  // 204
}
```

Key mapping rules:
- MuleSoft httpStatus variable maps to ResponseEntity status methods.
- 200 OK: ResponseEntity.ok(body)
- 201 Created: ResponseEntity.created(location).body(body)
- 204 No Content: ResponseEntity.noContent().build()
- 404 Not Found: ResponseEntity.notFound().build()
- Custom headers: ResponseEntity.ok().header("X-Custom", "value").body(body)""",
    },
    {
        "title": "Exception Hierarchy Design",
        "category": "springboot",
        "content": """MuleSoft Error Types -> Spring Boot Exception Hierarchy

MuleSoft error types:
```xml
<!-- HTTP:NOT_FOUND, HTTP:BAD_REQUEST, HTTP:UNAUTHORIZED, APP:BUSINESS_ERROR, DB:QUERY_EXECUTION -->
```

Spring Boot Java:
```java
// Base exception
public abstract class BaseException extends RuntimeException {
    private final String errorCode;
    private final HttpStatus status;
    public BaseException(String message, String errorCode, HttpStatus status) {
        super(message);
        this.errorCode = errorCode;
        this.status = status;
    }
}

// 404
public class ResourceNotFoundException extends BaseException {
    public ResourceNotFoundException(String resource, Object id) {
        super(resource + " not found: " + id, "NOT_FOUND", HttpStatus.NOT_FOUND);
    }
}

// 400
public class BadRequestException extends BaseException {
    public BadRequestException(String message) {
        super(message, "BAD_REQUEST", HttpStatus.BAD_REQUEST);
    }
}

// 409
public class ConflictException extends BaseException {
    public ConflictException(String message) {
        super(message, "CONFLICT", HttpStatus.CONFLICT);
    }
}

// 422
public class BusinessException extends BaseException {
    public BusinessException(String message) {
        super(message, "BUSINESS_ERROR", HttpStatus.UNPROCESSABLE_ENTITY);
    }
}

@ControllerAdvice
public class GlobalExceptionHandler {
    @ExceptionHandler(BaseException.class)
    public ResponseEntity<ErrorResponse> handleBase(BaseException ex) {
        return ResponseEntity.status(ex.getStatus())
            .body(new ErrorResponse(ex.getStatus().value(), ex.getErrorCode(), ex.getMessage()));
    }
}
```

Key mapping rules:
- MuleSoft error type namespace (HTTP, APP, DB) maps to exception class hierarchy.
- Create a BaseException with errorCode and HttpStatus.
- Each MuleSoft error type maps to a specific exception subclass.
- Single @ExceptionHandler on BaseException handles all custom exceptions.""",
    },
    {
        "title": "Async Processing with @Async",
        "category": "springboot",
        "content": """MuleSoft Async Scope -> Spring Boot @Async + CompletableFuture

MuleSoft XML:
```xml
<flow name="orderFlow">
    <http:listener config-ref="HTTP_Listener" path="/api/orders" method="POST"/>
    <db:insert config-ref="Database_Config">
        <db:sql>INSERT INTO orders ...</db:sql>
    </db:insert>
    <async>
        <flow-ref name="sendEmailSubflow"/>
        <flow-ref name="updateAnalyticsSubflow"/>
    </async>
    <set-payload value='{"status": "created"}'/>
</flow>
```

Spring Boot Java:
```java
@Service
public class OrderService {
    private final EmailService emailService;
    private final AnalyticsService analyticsService;

    public OrderDTO createOrder(CreateOrderRequest request) {
        Order saved = orderRepository.save(toEntity(request));
        // Fire and forget async tasks
        emailService.sendOrderConfirmationAsync(saved);
        analyticsService.trackOrderAsync(saved);
        return toDTO(saved);
    }
}

@Service
@Slf4j
public class EmailService {
    @Async
    public CompletableFuture<Void> sendOrderConfirmationAsync(Order order) {
        log.info("Sending confirmation email for order {}", order.getId());
        // send email logic
        return CompletableFuture.completedFuture(null);
    }
}
```

Key mapping rules:
- MuleSoft async scope maps to @Async annotated methods.
- Flow continues immediately after invoking async methods.
- Configure thread pool via AsyncConfigurer or ThreadPoolTaskExecutor.
- Return CompletableFuture for async results; void for fire-and-forget.""",
    },
    {
        "title": "Caching with @Cacheable",
        "category": "springboot",
        "content": """MuleSoft Cache Scope -> Spring Boot @Cacheable

MuleSoft XML:
```xml
<ee:cache cachingStrategy-ref="cacheConfig">
    <http:request config-ref="External_API" path="/v1/config" method="GET"/>
</ee:cache>
<ee:object-store-caching-strategy name="cacheConfig" maxEntries="100" entryTtl="300" entryTtlUnit="SECONDS"/>
```

Spring Boot Java:
```java
@Service
public class ConfigService {

    @Cacheable(value = "appConfig", key = "#configKey")
    public ConfigDTO getConfig(String configKey) {
        log.info("Cache miss - fetching config: {}", configKey);
        return webClient.get().uri("/v1/config/{key}", configKey)
            .retrieve().bodyToMono(ConfigDTO.class).block();
    }

    @CacheEvict(value = "appConfig", key = "#configKey")
    public void refreshConfig(String configKey) {
        log.info("Evicting cache for: {}", configKey);
    }

    @CacheEvict(value = "appConfig", allEntries = true)
    public void clearAllConfig() {
        log.info("Clearing all config cache");
    }
}
```

Key mapping rules:
- MuleSoft ee:cache scope maps to @Cacheable annotation on methods.
- cachingStrategy maxEntries and entryTtl map to cache manager configuration.
- @CacheEvict for manual cache invalidation.
- @CachePut to update cache without skipping method execution.""",
    },
    {
        "title": "Scheduling with @Scheduled",
        "category": "springboot",
        "content": """MuleSoft Scheduler -> Spring Boot @Scheduled

MuleSoft XML:
```xml
<flow name="cleanupFlow">
    <scheduler>
        <scheduling-strategy>
            <cron expression="0 0 2 * * *" timeZone="UTC"/>
        </scheduling-strategy>
    </scheduler>
    <db:delete config-ref="Database_Config">
        <db:sql>DELETE FROM sessions WHERE expires_at &lt; NOW()</db:sql>
    </db:delete>
    <logger message="Cleanup complete"/>
</flow>
```

Spring Boot Java:
```java
@Component
@Slf4j
public class ScheduledCleanup {
    private final SessionRepository sessionRepository;

    @Scheduled(cron = "0 0 2 * * *", zone = "UTC")
    public void cleanExpiredSessions() {
        int deleted = sessionRepository.deleteExpired(LocalDateTime.now());
        log.info("Cleanup complete: {} sessions removed", deleted);
    }

    @Scheduled(fixedRate = 60000)
    public void heartbeat() {
        log.debug("Service heartbeat");
    }
}
```

Key mapping rules:
- MuleSoft scheduler with cron maps to @Scheduled(cron).
- Cron expressions use 6 fields: second minute hour day month weekday.
- timeZone maps to zone parameter.
- fixed-frequency maps to fixedRate or fixedDelay.""",
    },
    {
        "title": "Event-Driven with @EventListener",
        "category": "springboot",
        "content": """MuleSoft VM Queue -> Spring Boot @EventListener

MuleSoft XML:
```xml
<vm:config name="VM_Config">
    <vm:queues><vm:queue queueName="auditQueue"/></vm:queues>
</vm:config>
<flow name="publishAudit">
    <vm:publish config-ref="VM_Config" queueName="auditQueue">
        <vm:content>#[{action: 'CREATE', entity: 'Order', entityId: payload.id}]</vm:content>
    </vm:publish>
</flow>
<flow name="consumeAudit">
    <vm:listener config-ref="VM_Config" queueName="auditQueue"/>
    <db:insert config-ref="Database_Config">
        <db:sql>INSERT INTO audit_log (action, entity, entity_id) VALUES (:action, :entity, :entityId)</db:sql>
    </db:insert>
</flow>
```

Spring Boot Java:
```java
public record AuditEvent(String action, String entity, Long entityId) {}

@Service
public class OrderService {
    private final ApplicationEventPublisher publisher;
    public OrderDTO create(CreateOrderRequest req) {
        Order saved = repository.save(toEntity(req));
        publisher.publishEvent(new AuditEvent("CREATE", "Order", saved.getId()));
        return toDTO(saved);
    }
}

@Component
@Slf4j
public class AuditEventListener {
    private final AuditRepository auditRepository;

    @EventListener
    public void onAuditEvent(AuditEvent event) {
        auditRepository.save(new AuditLog(event.action(), event.entity(), event.entityId()));
        log.info("Audit logged: {} {} {}", event.action(), event.entity(), event.entityId());
    }

    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void onAuditAfterCommit(AuditEvent event) {
        // Only fires after the transaction commits
    }
}
```

Key mapping rules:
- MuleSoft VM publish maps to ApplicationEventPublisher.publishEvent().
- VM listener maps to @EventListener method.
- @TransactionalEventListener for events tied to transaction lifecycle.
- Use @Async on listener for non-blocking event processing.""",
    },
    {
        "title": "WebSocket Support",
        "category": "springboot",
        "content": """MuleSoft WebSocket -> Spring Boot WebSocket

MuleSoft XML:
```xml
<websocket:config name="WS_Config">
    <websocket:connection>
        <websocket:listener host="0.0.0.0" port="8081" path="/ws"/>
    </websocket:connection>
</websocket:config>
<flow name="wsFlow">
    <websocket:on-inbound-message config-ref="WS_Config" path="/ws/notifications"/>
    <logger message="WS message: #[payload]"/>
</flow>
```

Spring Boot Java:
```java
@Configuration
@EnableWebSocketMessageBroker
public class WebSocketConfig implements WebSocketMessageBrokerConfigurer {
    @Override
    public void configureMessageBroker(MessageBrokerRegistry config) {
        config.enableSimpleBroker("/topic");
        config.setApplicationDestinationPrefixes("/app");
    }
    @Override
    public void registerStompEndpoints(StompEndpointRegistry registry) {
        registry.addEndpoint("/ws").setAllowedOrigins("*").withSockJS();
    }
}

@Controller
public class NotificationController {
    private final SimpMessagingTemplate messagingTemplate;

    @MessageMapping("/notify")
    @SendTo("/topic/notifications")
    public NotificationDTO handleMessage(NotificationDTO message) {
        return message;
    }

    // Push from server:
    public void pushNotification(NotificationDTO notification) {
        messagingTemplate.convertAndSend("/topic/notifications", notification);
    }
}
```

Key mapping rules:
- MuleSoft websocket:config maps to @EnableWebSocketMessageBroker.
- websocket:on-inbound-message maps to @MessageMapping.
- Server push maps to SimpMessagingTemplate.convertAndSend().
- Use STOMP protocol with SockJS fallback for broad browser support.""",
    },
    {
        "title": "File Upload Handling",
        "category": "springboot",
        "content": """MuleSoft File/Multipart Handling -> Spring Boot MultipartFile

MuleSoft XML:
```xml
<flow name="uploadFlow">
    <http:listener config-ref="HTTP_Listener" path="/api/files/upload" method="POST"/>
    <set-variable variableName="filePart" value="#[payload.parts.file]"/>
    <set-variable variableName="metadata" value="#[payload.parts.metadata.content]"/>
    <file:write config-ref="File_Config" path="#['/uploads/' ++ vars.filePart.headers.'Content-Disposition'.filename]">
        <file:content>#[vars.filePart.content]</file:content>
    </file:write>
</flow>
```

Spring Boot Java:
```java
@RestController
@RequestMapping("/api/files")
public class FileController {

    @PostMapping(value = "/upload", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<FileResponse> upload(
            @RequestParam("file") MultipartFile file,
            @RequestParam(value = "metadata", required = false) String metadata) {
        if (file.isEmpty()) {
            throw new BadRequestException("File is empty");
        }
        FileResponse response = fileService.store(file, metadata);
        return ResponseEntity.status(HttpStatus.CREATED).body(response);
    }

    @PostMapping(value = "/upload-multiple", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<List<FileResponse>> uploadMultiple(
            @RequestParam("files") List<MultipartFile> files) {
        List<FileResponse> responses = files.stream()
            .map(f -> fileService.store(f, null)).collect(Collectors.toList());
        return ResponseEntity.status(HttpStatus.CREATED).body(responses);
    }
}
```

application.yml:
```yaml
spring:
  servlet:
    multipart:
      max-file-size: 10MB
      max-request-size: 50MB
```

Key mapping rules:
- MuleSoft payload.parts.file maps to @RequestParam("file") MultipartFile.
- Multiple files map to List<MultipartFile> parameter.
- File size limits configured in application.yml.
- Store files to disk, cloud storage, or database via FileStorageService.""",
    },
    {
        "title": "Internationalization i18n",
        "category": "springboot",
        "content": """MuleSoft Localization -> Spring Boot i18n

MuleSoft XML:
```xml
<flow name="localizedFlow">
    <set-variable variableName="locale" value="#[attributes.headers.'Accept-Language' default 'en']"/>
    <choice>
        <when expression="#[vars.locale startsWith 'es']">
            <set-payload value='{"message": "Pedido creado exitosamente"}'/>
        </when>
        <otherwise>
            <set-payload value='{"message": "Order created successfully"}'/>
        </otherwise>
    </choice>
</flow>
```

Spring Boot Java:
```java
// messages.properties (default - English)
// order.created=Order created successfully

// messages_es.properties
// order.created=Pedido creado exitosamente

@Service
public class OrderService {
    private final MessageSource messageSource;

    public String getLocalizedMessage(String key, Locale locale) {
        return messageSource.getMessage(key, null, locale);
    }
}

@RestController
public class OrderController {
    @PostMapping("/orders")
    public ResponseEntity<Map<String, String>> createOrder(
            @RequestBody CreateOrderRequest request, Locale locale) {
        orderService.create(request);
        String message = messageSource.getMessage("order.created", null, locale);
        return ResponseEntity.ok(Map.of("message", message));
    }
}

@Configuration
public class LocaleConfig implements WebMvcConfigurer {
    @Bean
    public LocaleResolver localeResolver() {
        AcceptHeaderLocaleResolver resolver = new AcceptHeaderLocaleResolver();
        resolver.setDefaultLocale(Locale.ENGLISH);
        return resolver;
    }
}
```

Key mapping rules:
- MuleSoft Accept-Language header logic maps to Spring MessageSource + LocaleResolver.
- Message files: messages.properties, messages_es.properties, etc.
- Locale auto-resolved from Accept-Language header.
- Use MessageSource.getMessage() for localized strings.""",
    },
    # ==================================================================
    #  7. Testing Patterns (15 docs)
    # ==================================================================
    {
        "title": "WebMvcTest for Controllers",
        "category": "testing",
        "content": """MuleSoft MUnit -> Spring Boot @WebMvcTest

MuleSoft MUnit:
```xml
<munit:test name="getOrdersTest" description="Test GET /orders">
    <munit:execution>
        <http:request method="GET" url="http://localhost:8081/api/orders"/>
    </munit:execution>
    <munit:validation>
        <munit-tools:assert-that expression="#[attributes.statusCode]" is="#[MunitTools::equalTo(200)]"/>
    </munit:validation>
</munit:test>
```

Spring Boot Java:
```java
@WebMvcTest(OrderController.class)
class OrderControllerTest {
    @Autowired private MockMvc mockMvc;
    @MockBean private OrderService orderService;

    @Test
    void getOrders_returnsOk() throws Exception {
        when(orderService.findAll()).thenReturn(List.of(new OrderDTO(1L, "ACTIVE")));
        mockMvc.perform(get("/api/orders"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$[0].id").value(1))
            .andExpect(jsonPath("$[0].status").value("ACTIVE"));
    }

    @Test
    void createOrder_returns201() throws Exception {
        CreateOrderRequest req = new CreateOrderRequest("customer1", List.of());
        when(orderService.create(any())).thenReturn(new OrderDTO(1L, "PENDING"));
        mockMvc.perform(post("/api/orders")
            .contentType(MediaType.APPLICATION_JSON)
            .content(objectMapper.writeValueAsString(req)))
            .andExpect(status().isCreated());
    }
}
```

Key mapping rules:
- MuleSoft MUnit HTTP tests map to @WebMvcTest with MockMvc.
- @MockBean mocks service layer dependencies.
- MUnit assert-that maps to MockMvc andExpect() assertions.
- @WebMvcTest loads only the web layer for fast testing.""",
    },
    {
        "title": "DataJpaTest for Repositories",
        "category": "testing",
        "content": """MuleSoft MUnit DB Test -> Spring Boot @DataJpaTest

MuleSoft MUnit:
```xml
<munit:test name="dbSelectTest">
    <munit:execution>
        <db:select config-ref="Database_Config">
            <db:sql>SELECT * FROM products WHERE category = 'ELECTRONICS'</db:sql>
        </db:select>
    </munit:execution>
    <munit:validation>
        <munit-tools:assert-that expression="#[sizeOf(payload)]" is="#[MunitTools::greaterThan(0)]"/>
    </munit:validation>
</munit:test>
```

Spring Boot Java:
```java
@DataJpaTest
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
class ProductRepositoryTest {
    @Autowired private ProductRepository repository;
    @Autowired private TestEntityManager entityManager;

    @Test
    void findByCategory_returnsProducts() {
        entityManager.persistAndFlush(new Product("Laptop", new BigDecimal("999.99"), "ELECTRONICS"));
        entityManager.persistAndFlush(new Product("Phone", new BigDecimal("499.99"), "ELECTRONICS"));

        List<Product> result = repository.findByCategory("ELECTRONICS");

        assertThat(result).hasSize(2);
        assertThat(result).extracting(Product::getCategory).containsOnly("ELECTRONICS");
    }
}
```

Key mapping rules:
- MuleSoft MUnit db tests map to @DataJpaTest with TestEntityManager.
- @DataJpaTest auto-configures an embedded DB or use Testcontainers.
- Test data setup uses entityManager.persistAndFlush().
- AssertJ provides fluent assertions for collections and objects.""",
    },
    {
        "title": "SpringBootTest for Integration Tests",
        "category": "testing",
        "content": """MuleSoft MUnit Integration -> Spring Boot @SpringBootTest

MuleSoft MUnit:
```xml
<munit:test name="integrationTest">
    <munit:execution>
        <flow-ref name="createOrderFlow"/>
    </munit:execution>
    <munit:validation>
        <munit-tools:assert-that expression="#[payload.status]" is="#[MunitTools::equalTo('CREATED')]"/>
    </munit:validation>
</munit:test>
```

Spring Boot Java:
```java
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class OrderIntegrationTest {
    @Autowired private TestRestTemplate restTemplate;
    @Autowired private OrderRepository orderRepository;

    @Test
    void createOrder_fullIntegration() {
        CreateOrderRequest request = new CreateOrderRequest("cust1", List.of(
            new OrderItemRequest("prod1", 2)));
        ResponseEntity<OrderDTO> response = restTemplate.postForEntity(
            "/api/orders", request, OrderDTO.class);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.CREATED);
        assertThat(response.getBody().getStatus()).isEqualTo("CREATED");
        assertThat(orderRepository.count()).isEqualTo(1);
    }
}
```

Key mapping rules:
- MuleSoft MUnit flow-ref integration maps to @SpringBootTest with full context.
- RANDOM_PORT starts a real HTTP server for end-to-end testing.
- TestRestTemplate makes real HTTP calls against the running application.
- Verify side effects (database state) with repository assertions.""",
    },
    {
        "title": "MockMvc for REST API Testing",
        "category": "testing",
        "content": """MuleSoft MUnit HTTP Assertions -> Spring Boot MockMvc

MuleSoft MUnit:
```xml
<munit:test name="testGetById">
    <munit:execution>
        <http:request method="GET" url="http://localhost:8081/api/products/1"/>
    </munit:execution>
    <munit:validation>
        <munit-tools:assert-that expression="#[attributes.statusCode]" is="#[MunitTools::equalTo(200)]"/>
        <munit-tools:assert-that expression="#[payload.name]" is="#[MunitTools::equalTo('Laptop')]"/>
    </munit:validation>
</munit:test>
```

Spring Boot Java:
```java
@WebMvcTest(ProductController.class)
class ProductControllerTest {
    @Autowired private MockMvc mockMvc;
    @MockBean private ProductService productService;

    @Test
    void getById_returnsProduct() throws Exception {
        when(productService.findById(1L)).thenReturn(new ProductDTO(1L, "Laptop", BigDecimal.valueOf(999)));
        mockMvc.perform(get("/api/products/{id}", 1))
            .andExpect(status().isOk())
            .andExpect(content().contentType(MediaType.APPLICATION_JSON))
            .andExpect(jsonPath("$.name").value("Laptop"))
            .andExpect(jsonPath("$.price").value(999));
    }

    @Test
    void getById_notFound() throws Exception {
        when(productService.findById(99L)).thenThrow(new ResourceNotFoundException("Product", 99L));
        mockMvc.perform(get("/api/products/{id}", 99))
            .andExpect(status().isNotFound());
    }
}
```

Key mapping rules:
- MuleSoft MUnit HTTP request/assertion maps to MockMvc perform/andExpect.
- StatusCode assertion maps to status().isOk(), status().isNotFound(), etc.
- Payload field assertions map to jsonPath("$.field").value().
- MockMvc tests run without starting a real HTTP server.""",
    },
    {
        "title": "Mockito for Service Testing",
        "category": "testing",
        "content": """MuleSoft MUnit Mocking -> Spring Boot Mockito

MuleSoft MUnit:
```xml
<munit:test name="testOrderService">
    <munit:behavior>
        <munit-tools:mock-when processor="db:select">
            <munit-tools:with-attributes>
                <munit-tools:with-attribute attributeName="config-ref" whereValue="Database_Config"/>
            </munit-tools:with-attributes>
            <munit-tools:then-return>
                <munit-tools:payload value="#[{id: 1, status: 'ACTIVE'}]"/>
            </munit-tools:then-return>
        </munit-tools:mock-when>
    </munit:behavior>
</munit:test>
```

Spring Boot Java:
```java
@ExtendWith(MockitoExtension.class)
class OrderServiceTest {
    @Mock private OrderRepository orderRepository;
    @Mock private PaymentService paymentService;
    @InjectMocks private OrderService orderService;

    @Test
    void createOrder_success() {
        when(orderRepository.save(any(Order.class))).thenReturn(new Order(1L, "ACTIVE"));
        when(paymentService.charge(any())).thenReturn(new PaymentResult("SUCCESS"));

        OrderDTO result = orderService.create(new CreateOrderRequest("cust1", List.of()));

        assertThat(result.getStatus()).isEqualTo("ACTIVE");
        verify(orderRepository).save(any(Order.class));
        verify(paymentService).charge(any());
    }

    @Test
    void createOrder_paymentFails() {
        when(paymentService.charge(any())).thenThrow(new PaymentException("Declined"));
        assertThrows(PaymentException.class, () -> orderService.create(new CreateOrderRequest("cust1", List.of())));
    }
}
```

Key mapping rules:
- MuleSoft MUnit mock-when maps to Mockito when().thenReturn().
- MUnit then-return maps to thenReturn() or thenThrow().
- @Mock creates mock instances; @InjectMocks wires them together.
- verify() ensures methods were called with expected arguments.""",
    },
    {
        "title": "Testcontainers for Database Tests",
        "category": "testing",
        "content": """MuleSoft MUnit DB Test -> Spring Boot Testcontainers

MuleSoft MUnit:
```xml
<munit:test name="dbIntegrationTest">
    <munit:behavior>
        <munit-tools:mock-when processor="db:select"/>
    </munit:behavior>
</munit:test>
```

Spring Boot Java:
```java
@SpringBootTest
@Testcontainers
class OrderRepositoryIntegrationTest {
    @Container
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:15")
        .withDatabaseName("testdb")
        .withUsername("test")
        .withPassword("test");

    @DynamicPropertySource
    static void configureProperties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", postgres::getJdbcUrl);
        registry.add("spring.datasource.username", postgres::getUsername);
        registry.add("spring.datasource.password", postgres::getPassword);
    }

    @Autowired private OrderRepository orderRepository;

    @Test
    void saveAndRetrieve() {
        Order order = new Order("PENDING", LocalDateTime.now());
        Order saved = orderRepository.save(order);
        Optional<Order> found = orderRepository.findById(saved.getId());
        assertThat(found).isPresent();
        assertThat(found.get().getStatus()).isEqualTo("PENDING");
    }
}
```

Key mapping rules:
- MuleSoft MUnit mocked DB calls map to Testcontainers real DB tests.
- @Container starts a PostgreSQL Docker container for the test.
- @DynamicPropertySource injects container connection details.
- Tests run against a real database instance for higher confidence.""",
    },
    {
        "title": "WireMock for External API Mocking",
        "category": "testing",
        "content": """MuleSoft MUnit HTTP Mock -> Spring Boot WireMock

MuleSoft MUnit:
```xml
<munit:test name="testExternalApiCall">
    <munit:behavior>
        <munit-tools:mock-when processor="http:request">
            <munit-tools:then-return>
                <munit-tools:payload value='{"data": "mocked"}'/>
            </munit-tools:then-return>
        </munit-tools:mock-when>
    </munit:behavior>
</munit:test>
```

Spring Boot Java:
```java
@SpringBootTest
@AutoConfigureWireMock(port = 0)
class ExternalApiClientTest {
    @Autowired private ExternalApiClient client;

    @Test
    void fetchData_success() {
        stubFor(get(urlEqualTo("/v1/data/123"))
            .willReturn(aResponse()
                .withStatus(200)
                .withHeader("Content-Type", "application/json")
                .withBody("{\"id\": 123, \"name\": \"Test\"}")));

        DataDTO result = client.fetchData("123");
        assertThat(result.getName()).isEqualTo("Test");
    }

    @Test
    void fetchData_serverError() {
        stubFor(get(urlPathMatching("/v1/data/.*"))
            .willReturn(aResponse().withStatus(500)));

        assertThrows(ServiceUnavailableException.class, () -> client.fetchData("456"));
    }
}
```

Key mapping rules:
- MuleSoft MUnit mock-when for HTTP maps to WireMock stubFor().
- Mocked response body maps to withBody().
- Mocked status code maps to withStatus().
- WireMock runs a real HTTP server; configure client baseUrl to point to it.""",
    },
    {
        "title": "RestClientTest for REST Client Testing",
        "category": "testing",
        "content": """MuleSoft MUnit REST Mock -> Spring Boot @RestClientTest

MuleSoft MUnit:
```xml
<munit:test name="testRestClient">
    <munit:behavior>
        <munit-tools:mock-when processor="http:request" doc:name="Mock API"/>
    </munit:behavior>
</munit:test>
```

Spring Boot Java:
```java
@RestClientTest(PaymentApiClient.class)
class PaymentApiClientTest {
    @Autowired private PaymentApiClient client;
    @Autowired private MockRestServiceServer server;
    @Autowired private ObjectMapper objectMapper;

    @Test
    void processPayment_success() throws Exception {
        PaymentResponse expected = new PaymentResponse("PAY-123", "SUCCESS");
        server.expect(requestTo("/v1/payments"))
            .andExpect(method(HttpMethod.POST))
            .andRespond(withSuccess(objectMapper.writeValueAsString(expected), MediaType.APPLICATION_JSON));

        PaymentResponse result = client.processPayment(new PaymentRequest(100.0, "USD"));
        assertThat(result.getStatus()).isEqualTo("SUCCESS");
        server.verify();
    }
}
```

Key mapping rules:
- MuleSoft MUnit mock-when for REST maps to @RestClientTest with MockRestServiceServer.
- server.expect() defines expected requests and mock responses.
- server.verify() ensures all expected requests were made.
- @RestClientTest only loads the REST client bean for focused testing.""",
    },
    {
        "title": "Test Fixtures and Data Builders",
        "category": "testing",
        "content": """MuleSoft MUnit Test Data -> Spring Boot Test Fixtures

MuleSoft MUnit:
```xml
<munit:test name="testWithFixture">
    <munit:behavior>
        <munit-tools:mock-when processor="db:select">
            <munit-tools:then-return>
                <munit-tools:payload value="#[readUrl('classpath://test-data/orders.json')]"/>
            </munit-tools:then-return>
        </munit-tools:mock-when>
    </munit:behavior>
</munit:test>
```

Spring Boot Java:
```java
public class TestDataBuilder {
    public static Order anOrder() {
        Order order = new Order();
        order.setId(1L);
        order.setStatus("ACTIVE");
        order.setCustomerId(100L);
        order.setCreatedAt(LocalDateTime.now());
        return order;
    }

    public static OrderDTO anOrderDTO() {
        return new OrderDTO(1L, "ACTIVE", 100L);
    }

    public static CreateOrderRequest aCreateOrderRequest() {
        return new CreateOrderRequest("cust1", List.of(
            new OrderItemRequest("prod1", 2, BigDecimal.TEN)));
    }
}

// Usage in tests:
@Test
void processOrder() {
    Order order = TestDataBuilder.anOrder();
    when(repository.findById(1L)).thenReturn(Optional.of(order));
    // ...
}
```

Key mapping rules:
- MuleSoft MUnit test data files map to Test Data Builder pattern.
- Centralize test data creation in builder classes for reuse.
- Builders avoid duplication and make tests more readable.
- Use @Sql annotation for database test data setup from SQL files.""",
    },
    {
        "title": "Parameterized Tests",
        "category": "testing",
        "content": """MuleSoft MUnit Multiple Scenarios -> Spring Boot @ParameterizedTest

MuleSoft MUnit:
```xml
<munit:test name="testStatusMapping1"><!-- test for ACTIVE --></munit:test>
<munit:test name="testStatusMapping2"><!-- test for INACTIVE --></munit:test>
<munit:test name="testStatusMapping3"><!-- test for PENDING --></munit:test>
```

Spring Boot Java:
```java
class StatusMapperTest {
    @ParameterizedTest
    @CsvSource({
        "ACTIVE, Active Order",
        "INACTIVE, Inactive Order",
        "PENDING, Pending Order",
        "CANCELLED, Cancelled Order"
    })
    void mapStatus_returnsCorrectLabel(String status, String expectedLabel) {
        String result = StatusMapper.toLabel(status);
        assertThat(result).isEqualTo(expectedLabel);
    }

    @ParameterizedTest
    @MethodSource("invalidInputs")
    void validate_rejectsInvalid(String input, String expectedError) {
        ValidationResult result = validator.validate(input);
        assertThat(result.getError()).isEqualTo(expectedError);
    }

    static Stream<Arguments> invalidInputs() {
        return Stream.of(
            Arguments.of("", "Input required"),
            Arguments.of(null, "Input required"),
            Arguments.of("x".repeat(256), "Input too long"));
    }
}
```

Key mapping rules:
- MuleSoft multiple MUnit tests for similar scenarios map to @ParameterizedTest.
- @CsvSource for simple input/expected pairs.
- @MethodSource for complex test data.
- Reduces test code duplication while covering more cases.""",
    },
    {
        "title": "Test Coverage Best Practices",
        "category": "testing",
        "content": """MuleSoft MUnit Coverage -> Spring Boot Test Coverage with JaCoCo

MuleSoft MUnit coverage:
```xml
<munit:config name="MUnit_Config">
    <munit:coverage requiredApplicationCoverage="80" requiredFlowCoverage="80"/>
</munit:config>
```

Spring Boot pom.xml:
```xml
<plugin>
    <groupId>org.jacoco</groupId>
    <artifactId>jacoco-maven-plugin</artifactId>
    <version>0.8.11</version>
    <executions>
        <execution>
            <goals><goal>prepare-agent</goal></goals>
        </execution>
        <execution>
            <id>report</id>
            <phase>verify</phase>
            <goals><goal>report</goal></goals>
        </execution>
        <execution>
            <id>check</id>
            <phase>verify</phase>
            <goals><goal>check</goal></goals>
            <configuration>
                <rules>
                    <rule>
                        <element>BUNDLE</element>
                        <limits>
                            <limit>
                                <counter>LINE</counter>
                                <value>COVEREDRATIO</value>
                                <minimum>0.80</minimum>
                            </limit>
                        </limits>
                    </rule>
                </rules>
            </configuration>
        </execution>
    </executions>
</plugin>
```

Test strategy:
```java
// Unit tests (fast, isolated) - 70% of tests
@ExtendWith(MockitoExtension.class)    // Service logic
@WebMvcTest                             // Controller endpoints

// Integration tests (slower, real deps) - 25% of tests
@DataJpaTest                            // Repository queries
@SpringBootTest                         // Full integration

// E2E tests (slowest) - 5% of tests
@SpringBootTest(webEnvironment = RANDOM_PORT)
```

Key mapping rules:
- MuleSoft MUnit coverage config maps to JaCoCo Maven plugin.
- requiredApplicationCoverage maps to JaCoCo minimum coverage rules.
- Aim for 80%+ line coverage as a minimum threshold.
- Use the test pyramid: many unit tests, fewer integration, fewest E2E.""",
    },
    {
        "title": "API Contract Testing with Spring Cloud Contract",
        "category": "testing",
        "content": """MuleSoft API Spec Testing -> Spring Cloud Contract

MuleSoft RAML API spec testing:
```xml
<munit:test name="testApiContract">
    <munit:execution>
        <http:request method="GET" url="http://localhost:8081/api/orders"/>
    </munit:execution>
    <munit:validation>
        <munit-tools:assert-that expression="#[attributes.statusCode]" is="#[MunitTools::equalTo(200)]"/>
    </munit:validation>
</munit:test>
```

Spring Boot contract (contracts/orders/shouldReturnOrders.groovy):
```groovy
Contract.make {
    description "should return list of orders"
    request {
        method GET()
        url "/api/orders"
        headers { contentType applicationJson() }
    }
    response {
        status OK()
        headers { contentType applicationJson() }
        body([
            [id: 1, status: "ACTIVE"],
            [id: 2, status: "PENDING"]
        ])
    }
}
```

Spring Boot Java (base test class):
```java
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.MOCK)
@AutoConfigureMockMvc
public abstract class ContractBaseTest {
    @Autowired private MockMvc mockMvc;
    @MockBean private OrderService orderService;

    @BeforeEach
    void setup() {
        when(orderService.findAll()).thenReturn(List.of(
            new OrderDTO(1L, "ACTIVE"), new OrderDTO(2L, "PENDING")));
        RestAssuredMockMvc.mockMvc(mockMvc);
    }
}
```

Key mapping rules:
- MuleSoft RAML-based testing maps to Spring Cloud Contract.
- Contract definitions generate both tests and stubs automatically.
- Producer verifies contract; consumer uses generated stubs.
- Ensures API changes don't break consumers.""",
    },
    {
        "title": "Security Testing with MockUser",
        "category": "testing",
        "content": """MuleSoft MUnit Security -> Spring Boot @WithMockUser

MuleSoft MUnit:
```xml
<munit:test name="testSecuredEndpoint">
    <munit:behavior>
        <munit-tools:mock-when processor="http:request">
            <munit-tools:with-attributes>
                <munit-tools:with-attribute attributeName="config-ref" whereValue="Auth_Config"/>
            </munit-tools:with-attributes>
        </munit-tools:mock-when>
    </munit:behavior>
</munit:test>
```

Spring Boot Java:
```java
@WebMvcTest(AdminController.class)
class AdminControllerSecurityTest {

    @Autowired private MockMvc mockMvc;
    @MockBean private AdminService adminService;

    @Test
    @WithMockUser(roles = "ADMIN")
    void adminEndpoint_withAdminRole_returnsOk() throws Exception {
        mockMvc.perform(get("/api/admin/users"))
            .andExpect(status().isOk());
    }

    @Test
    @WithMockUser(roles = "USER")
    void adminEndpoint_withUserRole_returnsForbidden() throws Exception {
        mockMvc.perform(get("/api/admin/users"))
            .andExpect(status().isForbidden());
    }

    @Test
    void adminEndpoint_noAuth_returnsUnauthorized() throws Exception {
        mockMvc.perform(get("/api/admin/users"))
            .andExpect(status().isUnauthorized());
    }
}
```

Key mapping rules:
- MuleSoft MUnit auth mocking maps to @WithMockUser annotation.
- Test different roles: ADMIN, USER, no auth.
- @WithMockUser populates SecurityContext for the test.
- Test both positive (authorized) and negative (unauthorized) cases.""",
    },
    {
        "title": "Test Configuration with @TestConfiguration",
        "category": "testing",
        "content": """MuleSoft MUnit Config Override -> Spring Boot @TestConfiguration

MuleSoft MUnit:
```xml
<munit:test name="testWithOverride">
    <munit:behavior>
        <munit-tools:mock-when processor="http:request" doc:name="Mock External API"/>
    </munit:behavior>
</munit:test>
```

Spring Boot Java:
```java
@TestConfiguration
public class TestConfig {
    @Bean
    @Primary
    public WebClient testWebClient() {
        return WebClient.builder().baseUrl("http://localhost:8089").build();
    }

    @Bean
    @Primary
    public Clock testClock() {
        return Clock.fixed(Instant.parse("2024-01-15T10:00:00Z"), ZoneId.of("UTC"));
    }
}

@SpringBootTest
@Import(TestConfig.class)
class OrderServiceIntegrationTest {
    @Autowired private OrderService orderService;

    @Test
    void createOrder_usesFixedClock() {
        OrderDTO order = orderService.create(new CreateOrderRequest("cust1", List.of()));
        assertThat(order.getCreatedAt()).isEqualTo("2024-01-15T10:00:00");
    }
}
```

Key mapping rules:
- MuleSoft MUnit config overrides map to @TestConfiguration beans.
- @Primary on test beans overrides production beans.
- Use @Import to include test configuration in specific tests.
- Fixed Clock bean makes time-dependent tests deterministic.""",
    },
    # ==================================================================
    #  8. Security Patterns (15 docs)
    # ==================================================================
    {
        "title": "Spring Security Basic Configuration",
        "category": "security",
        "content": """MuleSoft HTTP Basic Auth -> Spring Security Configuration

MuleSoft XML:
```xml
<http:listener-config name="Secured_Listener">
    <http:listener-connection host="0.0.0.0" port="8081"/>
    <http:listener-interceptors>
        <http:basic-security-filter realm="myApp"/>
    </http:listener-interceptors>
</http:listener-config>
```

Spring Boot Java:
```java
@Configuration
@EnableWebSecurity
public class SecurityConfig {

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        return http
            .csrf(csrf -> csrf.disable())
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/api/public/**").permitAll()
                .requestMatchers("/actuator/health").permitAll()
                .requestMatchers("/api/admin/**").hasRole("ADMIN")
                .anyRequest().authenticated())
            .httpBasic(Customizer.withDefaults())
            .build();
    }

    @Bean
    public PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder();
    }
}
```

Key mapping rules:
- MuleSoft basic-security-filter maps to .httpBasic() in SecurityFilterChain.
- Path-based access control maps to authorizeHttpRequests() with matchers.
- Always disable CSRF for stateless REST APIs.
- Use BCryptPasswordEncoder for password hashing.""",
    },
    {
        "title": "JWT Authentication Filter",
        "category": "security",
        "content": """MuleSoft JWT Validation -> Spring Boot JWT Filter

MuleSoft XML:
```xml
<flow name="jwtValidation">
    <http:listener config-ref="HTTP_Listener" path="/api/secure" method="GET"/>
    <set-variable variableName="token" value="#[attributes.headers.Authorization replace 'Bearer ' with '']"/>
    <jwt:validate config-ref="JWT_Config" token="#[vars.token]"/>
</flow>
```

Spring Boot Java:
```java
@Component
public class JwtAuthenticationFilter extends OncePerRequestFilter {
    private final JwtTokenProvider tokenProvider;

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
            FilterChain filterChain) throws ServletException, IOException {
        String token = extractToken(request);
        if (token != null && tokenProvider.validateToken(token)) {
            String username = tokenProvider.getUsername(token);
            List<String> roles = tokenProvider.getRoles(token);
            UsernamePasswordAuthenticationToken auth = new UsernamePasswordAuthenticationToken(
                username, null, roles.stream().map(SimpleGrantedAuthority::new).toList());
            SecurityContextHolder.getContext().setAuthentication(auth);
        }
        filterChain.doFilter(request, response);
    }

    private String extractToken(HttpServletRequest request) {
        String header = request.getHeader("Authorization");
        if (header != null && header.startsWith("Bearer ")) {
            return header.substring(7);
        }
        return null;
    }
}

@Component
public class JwtTokenProvider {
    @Value("${jwt.secret}") private String secret;
    @Value("${jwt.expiration}") private long expiration;

    public boolean validateToken(String token) {
        try {
            Jwts.parserBuilder().setSigningKey(Keys.hmacShaKeyFor(secret.getBytes()))
                .build().parseClaimsJws(token);
            return true;
        } catch (JwtException e) { return false; }
    }

    public String getUsername(String token) {
        return Jwts.parserBuilder().setSigningKey(Keys.hmacShaKeyFor(secret.getBytes()))
            .build().parseClaimsJws(token).getBody().getSubject();
    }
}
```

Key mapping rules:
- MuleSoft jwt:validate maps to a custom OncePerRequestFilter.
- Token extraction from Authorization header is identical.
- Use jjwt library for JWT parsing and validation.
- Register the filter before UsernamePasswordAuthenticationFilter in the chain.""",
    },
    {
        "title": "OAuth2 Resource Server",
        "category": "security",
        "content": """MuleSoft OAuth2 Provider Validation -> Spring Boot OAuth2 Resource Server

MuleSoft XML:
```xml
<oauth2-provider:config name="OAuth2_Config" providerName="myProvider"
    tokenUrl="https://auth.example.com/oauth/token"
    validateTokenUrl="https://auth.example.com/oauth/check_token"/>
<flow name="oauth2SecuredFlow">
    <http:listener config-ref="HTTP_Listener" path="/api/resource" method="GET"/>
    <oauth2-provider:validate-token config-ref="OAuth2_Config"/>
</flow>
```

Spring Boot Java:
```java
@Configuration
@EnableWebSecurity
public class OAuth2ResourceServerConfig {
    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        return http
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/api/public/**").permitAll()
                .anyRequest().authenticated())
            .oauth2ResourceServer(oauth2 -> oauth2
                .jwt(jwt -> jwt.jwtAuthenticationConverter(jwtAuthConverter())))
            .build();
    }

    @Bean
    public JwtAuthenticationConverter jwtAuthConverter() {
        JwtGrantedAuthoritiesConverter grantedAuthoritiesConverter = new JwtGrantedAuthoritiesConverter();
        grantedAuthoritiesConverter.setAuthorityPrefix("ROLE_");
        grantedAuthoritiesConverter.setAuthoritiesClaimName("roles");
        JwtAuthenticationConverter converter = new JwtAuthenticationConverter();
        converter.setJwtGrantedAuthoritiesConverter(grantedAuthoritiesConverter);
        return converter;
    }
}
```

application.yml:
```yaml
spring:
  security:
    oauth2:
      resourceserver:
        jwt:
          issuer-uri: https://auth.example.com
          jwk-set-uri: https://auth.example.com/.well-known/jwks.json
```

Key mapping rules:
- MuleSoft oauth2-provider:validate-token maps to .oauth2ResourceServer().jwt().
- Token validation URL maps to jwk-set-uri for JWK-based validation.
- Roles extraction maps to JwtGrantedAuthoritiesConverter.
- Spring Security handles token validation automatically.""",
    },
    {
        "title": "OAuth2 Client Social Login",
        "category": "security",
        "content": """MuleSoft OAuth2 Client -> Spring Boot OAuth2 Client

MuleSoft XML:
```xml
<oauth2:config name="OAuth2_Client">
    <oauth2:authorization-code-grant-type
        clientId="${oauth.clientId}" clientSecret="${oauth.clientSecret}"
        tokenUrl="https://accounts.google.com/o/oauth2/token"
        authorizationUrl="https://accounts.google.com/o/oauth2/auth"/>
</oauth2:config>
```

Spring Boot application.yml:
```yaml
spring:
  security:
    oauth2:
      client:
        registration:
          google:
            client-id: ${GOOGLE_CLIENT_ID}
            client-secret: ${GOOGLE_CLIENT_SECRET}
            scope: openid,profile,email
          github:
            client-id: ${GITHUB_CLIENT_ID}
            client-secret: ${GITHUB_CLIENT_SECRET}
```

Spring Boot Java:
```java
@Configuration
@EnableWebSecurity
public class OAuth2LoginConfig {
    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        return http
            .authorizeHttpRequests(auth -> auth.anyRequest().authenticated())
            .oauth2Login(oauth2 -> oauth2
                .userInfoEndpoint(userInfo -> userInfo
                    .userService(customOAuth2UserService())))
            .build();
    }

    @Bean
    public OAuth2UserService<OAuth2UserRequest, OAuth2User> customOAuth2UserService() {
        return new CustomOAuth2UserService();
    }
}
```

Key mapping rules:
- MuleSoft OAuth2 authorization-code-grant maps to spring.security.oauth2.client.
- Client ID and secret map to registration properties.
- Google, GitHub, Facebook have auto-configured providers.
- Custom user service maps user info to your domain model.""",
    },
    {
        "title": "Role-Based Access Control with @PreAuthorize",
        "category": "security",
        "content": """MuleSoft Role Check -> Spring Boot @PreAuthorize

MuleSoft XML:
```xml
<flow name="adminFlow">
    <http:listener config-ref="HTTP_Listener" path="/api/admin/users" method="GET"/>
    <choice>
        <when expression="#[!vars.userRoles contains 'ADMIN']">
            <raise-error type="HTTP:FORBIDDEN" description="Admin role required"/>
        </when>
    </choice>
</flow>
```

Spring Boot Java:
```java
@RestController
@RequestMapping("/api/admin")
public class AdminController {

    @PreAuthorize("hasRole('ADMIN')")
    @GetMapping("/users")
    public ResponseEntity<List<UserDTO>> getAllUsers() {
        return ResponseEntity.ok(userService.findAll());
    }

    @PreAuthorize("hasAnyRole('ADMIN', 'MANAGER')")
    @GetMapping("/reports")
    public ResponseEntity<List<ReportDTO>> getReports() {
        return ResponseEntity.ok(reportService.findAll());
    }

    @PreAuthorize("#userId == authentication.principal.id or hasRole('ADMIN')")
    @GetMapping("/users/{userId}")
    public ResponseEntity<UserDTO> getUser(@PathVariable Long userId) {
        return ResponseEntity.ok(userService.findById(userId));
    }
}

@Configuration
@EnableMethodSecurity
public class MethodSecurityConfig {}
```

Key mapping rules:
- MuleSoft role check in choice router maps to @PreAuthorize annotation.
- hasRole('ADMIN') checks for ROLE_ADMIN authority.
- hasAnyRole() for multiple allowed roles.
- SpEL expressions for complex authorization logic.
- Enable with @EnableMethodSecurity.""",
    },
    {
        "title": "Method-Level Security with @Secured",
        "category": "security",
        "content": """MuleSoft Flow-Level Security -> Spring Boot @Secured

MuleSoft XML:
```xml
<flow name="sensitiveOperation">
    <choice>
        <when expression="#[vars.userRoles contains 'MANAGER']">
            <flow-ref name="processApproval"/>
        </when>
        <otherwise>
            <raise-error type="HTTP:FORBIDDEN"/>
        </otherwise>
    </choice>
</flow>
```

Spring Boot Java:
```java
@Service
public class ApprovalService {

    @Secured("ROLE_MANAGER")
    public ApprovalResult processApproval(ApprovalRequest request) {
        // Only managers can execute this
        return doProcess(request);
    }

    @Secured({"ROLE_ADMIN", "ROLE_MANAGER"})
    public void deleteRecord(Long id) {
        repository.deleteById(id);
    }

    @PreAuthorize("hasRole('ADMIN') and #amount < 10000 or hasRole('DIRECTOR')")
    public TransferResult transferFunds(BigDecimal amount) {
        return executeTransfer(amount);
    }
}
```

Key mapping rules:
- MuleSoft choice on role maps to @Secured on service methods.
- @Secured is simpler; @PreAuthorize supports SpEL expressions.
- Method-level security secures the service layer, not just controllers.
- Access denied throws AccessDeniedException (mapped to 403 Forbidden).""",
    },
    {
        "title": "CORS Configuration in Security",
        "category": "security",
        "content": """MuleSoft CORS -> Spring Security CORS Configuration

MuleSoft XML:
```xml
<http:listener-interceptors>
    <http:cors-interceptor>
        <http:origins>
            <http:origin url="https://app.example.com"/>
        </http:origins>
    </http:cors-interceptor>
</http:listener-interceptors>
```

Spring Boot Java:
```java
@Configuration
@EnableWebSecurity
public class SecurityConfig {
    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        return http
            .cors(cors -> cors.configurationSource(corsConfigurationSource()))
            .csrf(csrf -> csrf.disable())
            .authorizeHttpRequests(auth -> auth.anyRequest().authenticated())
            .build();
    }

    @Bean
    public CorsConfigurationSource corsConfigurationSource() {
        CorsConfiguration config = new CorsConfiguration();
        config.setAllowedOrigins(List.of("https://app.example.com"));
        config.setAllowedMethods(List.of("GET", "POST", "PUT", "DELETE", "OPTIONS"));
        config.setAllowedHeaders(List.of("Authorization", "Content-Type"));
        config.setAllowCredentials(true);
        config.setMaxAge(3600L);
        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/api/**", config);
        return source;
    }
}
```

Key mapping rules:
- MuleSoft cors-interceptor maps to CorsConfigurationSource bean.
- Must configure CORS in both Spring Security and WebMvc for it to work.
- Spring Security CORS filter runs before other security filters.
- setAllowCredentials(true) required for cookie/token authentication.""",
    },
    {
        "title": "CSRF Protection",
        "category": "security",
        "content": """MuleSoft CSRF -> Spring Security CSRF Configuration

MuleSoft XML:
```xml
<!-- MuleSoft does not have built-in CSRF protection for REST APIs -->
```

Spring Boot Java:
```java
@Configuration
@EnableWebSecurity
public class SecurityConfig {
    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        return http
            // For stateless REST APIs, disable CSRF
            .csrf(csrf -> csrf.disable())
            .sessionManagement(session -> session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
            .build();
    }

    // For server-rendered apps with sessions, enable CSRF:
    @Bean
    public SecurityFilterChain webFilterChain(HttpSecurity http) throws Exception {
        return http
            .csrf(csrf -> csrf
                .csrfTokenRepository(CookieCsrfTokenRepository.withHttpOnlyFalse())
                .ignoringRequestMatchers("/api/webhooks/**"))
            .build();
    }
}
```

Key mapping rules:
- Stateless REST APIs should disable CSRF (token-based auth is not vulnerable).
- Session-based apps must enable CSRF with CookieCsrfTokenRepository.
- Webhook endpoints often need CSRF exemption with ignoringRequestMatchers.
- MuleSoft REST APIs are stateless and don't need CSRF; same for Spring Boot REST.""",
    },
    {
        "title": "Password Encoding with BCrypt",
        "category": "security",
        "content": """MuleSoft Password Handling -> Spring Boot BCrypt

MuleSoft XML:
```xml
<flow name="registerUser">
    <ee:transform>
        <ee:set-variable variableName="hashedPassword"><![CDATA[%dw 2.0
import dw::Crypto
---
Crypto::hashWith(payload.password, "SHA-256")]]></ee:set-variable>
    </ee:transform>
    <db:insert config-ref="Database_Config">
        <db:sql>INSERT INTO users (username, password_hash) VALUES (:username, :hash)</db:sql>
        <db:input-parameters><![CDATA[#[{username: payload.username, hash: vars.hashedPassword}]]]></db:input-parameters>
    </db:insert>
</flow>
```

Spring Boot Java:
```java
@Service
public class UserService {
    private final PasswordEncoder passwordEncoder;
    private final UserRepository userRepository;

    public UserDTO register(RegisterRequest request) {
        if (userRepository.existsByUsername(request.getUsername())) {
            throw new ConflictException("Username already taken");
        }
        User user = new User();
        user.setUsername(request.getUsername());
        user.setPasswordHash(passwordEncoder.encode(request.getPassword()));
        User saved = userRepository.save(user);
        return toDTO(saved);
    }

    public boolean verifyPassword(String rawPassword, String encodedPassword) {
        return passwordEncoder.matches(rawPassword, encodedPassword);
    }
}

@Bean
public PasswordEncoder passwordEncoder() {
    return new BCryptPasswordEncoder(12); // strength 12
}
```

Key mapping rules:
- MuleSoft SHA-256 hashing is weak; use BCrypt in Spring Boot instead.
- BCryptPasswordEncoder handles salt generation automatically.
- passwordEncoder.encode() for hashing; .matches() for verification.
- Never use MD5 or SHA for password hashing; always use BCrypt or Argon2.""",
    },
    {
        "title": "API Key Authentication",
        "category": "security",
        "content": """MuleSoft Client ID Enforcement -> Spring Boot API Key Filter

MuleSoft XML:
```xml
<api-gateway:client-id-enforcement config-ref="API_Gateway"
    clientIdExpression="#[attributes.headers.'X-API-Key']"/>
```

Spring Boot Java:
```java
@Component
public class ApiKeyAuthFilter extends OncePerRequestFilter {
    @Value("${api.keys}") private List<String> validApiKeys;

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
            FilterChain chain) throws ServletException, IOException {
        String apiKey = request.getHeader("X-API-Key");
        if (apiKey == null || !validApiKeys.contains(apiKey)) {
            response.setStatus(HttpStatus.UNAUTHORIZED.value());
            response.getWriter().write("{\"error\": \"Invalid API key\"}");
            return;
        }
        chain.doFilter(request, response);
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        return request.getRequestURI().startsWith("/api/public/");
    }
}
```

Key mapping rules:
- MuleSoft client-id-enforcement maps to a custom API key filter.
- X-API-Key header maps to request.getHeader("X-API-Key").
- Validate against a whitelist of known API keys.
- shouldNotFilter() excludes public endpoints from API key check.""",
    },
    {
        "title": "Rate Limiting with Bucket4j",
        "category": "security",
        "content": """MuleSoft Throttling Policy -> Spring Boot Rate Limiting

MuleSoft XML (API policy):
```xml
<api-gateway:throttling-policy maxRequests="100" timePeriodInMilliseconds="60000"/>
```

Spring Boot Java:
```java
@Component
public class RateLimitFilter extends OncePerRequestFilter {
    private final Map<String, Bucket> buckets = new ConcurrentHashMap<>();

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
            FilterChain chain) throws ServletException, IOException {
        String clientId = request.getHeader("X-Client-ID");
        if (clientId == null) clientId = request.getRemoteAddr();

        Bucket bucket = buckets.computeIfAbsent(clientId, k -> createBucket());
        if (bucket.tryConsume(1)) {
            chain.doFilter(request, response);
        } else {
            response.setStatus(HttpStatus.TOO_MANY_REQUESTS.value());
            response.setHeader("Retry-After", "60");
            response.getWriter().write("{\"error\": \"Rate limit exceeded\"}");
        }
    }

    private Bucket createBucket() {
        return Bucket.builder()
            .addLimit(Bandwidth.classic(100, Refill.intervally(100, Duration.ofMinutes(1))))
            .build();
    }
}
```

Key mapping rules:
- MuleSoft throttling-policy maps to Bucket4j rate limiter.
- maxRequests per time period maps to Bandwidth.classic() configuration.
- Return 429 Too Many Requests with Retry-After header.
- Use client ID or IP address as the rate limit key.""",
    },
    {
        "title": "Input Sanitization",
        "category": "security",
        "content": """MuleSoft Input Validation -> Spring Boot Input Sanitization

MuleSoft XML:
```xml
<validation:matches-regex value="#[payload.name]" regex="^[a-zA-Z0-9 ]+$" message="Invalid characters"/>
```

Spring Boot Java:
```java
@Component
public class InputSanitizer {
    public String sanitize(String input) {
        if (input == null) return null;
        // Remove HTML tags
        String cleaned = Jsoup.clean(input, Safelist.none());
        // Trim and limit length
        return cleaned.trim().substring(0, Math.min(cleaned.length(), 1000));
    }
}

// Or use validation annotations:
public class CreatePostRequest {
    @NotBlank
    @Size(max = 1000)
    @Pattern(regexp = "^[a-zA-Z0-9 .,!?'-]+$", message = "Invalid characters in title")
    private String title;

    @NotBlank
    @Size(max = 10000)
    private String content; // sanitized by service layer
}

@Service
public class PostService {
    private final InputSanitizer sanitizer;

    public PostDTO create(CreatePostRequest request) {
        Post post = new Post();
        post.setTitle(sanitizer.sanitize(request.getTitle()));
        post.setContent(sanitizer.sanitize(request.getContent()));
        return toDTO(repository.save(post));
    }
}
```

Key mapping rules:
- MuleSoft regex validation maps to @Pattern annotation.
- Additional sanitization with Jsoup for HTML stripping.
- Always sanitize user input before storage.
- Use @Size to limit input length and prevent oversized payloads.""",
    },
    {
        "title": "SQL Injection Prevention",
        "category": "security",
        "content": """MuleSoft Parameterized Queries -> Spring Boot Parameterized Queries

MuleSoft XML (SAFE - parameterized):
```xml
<db:select config-ref="Database_Config">
    <db:sql>SELECT * FROM users WHERE username = :username</db:sql>
    <db:input-parameters><![CDATA[#[{username: payload.username}]]]></db:input-parameters>
</db:select>
```

MuleSoft XML (UNSAFE - concatenation):
```xml
<db:select config-ref="Database_Config">
    <db:sql>SELECT * FROM users WHERE username = '#[payload.username]'</db:sql>
</db:select>
```

Spring Boot Java (SAFE):
```java
// JPA - automatically parameterized
public interface UserRepository extends JpaRepository<User, Long> {
    Optional<User> findByUsername(String username); // SAFE
    @Query("SELECT u FROM User u WHERE u.username = :username") // SAFE
    Optional<User> findUser(@Param("username") String username);
}

// JdbcTemplate - use ? placeholders
jdbcTemplate.queryForObject("SELECT * FROM users WHERE username = ?",
    new Object[]{username}, User.class); // SAFE

// UNSAFE - NEVER do this:
// jdbcTemplate.query("SELECT * FROM users WHERE username = '" + username + "'", ...);
```

Key mapping rules:
- MuleSoft :param input-parameters map to JPA @Param or JdbcTemplate ? placeholders.
- NEVER concatenate user input into SQL strings.
- JPA derived queries and @Query with @Param are always safe.
- JdbcTemplate with ? placeholders and Object[] args is safe.""",
    },
    {
        "title": "XSS Prevention",
        "category": "security",
        "content": """MuleSoft Output Encoding -> Spring Boot XSS Prevention

MuleSoft XML:
```xml
<!-- MuleSoft does not have built-in XSS protection -->
<ee:transform>
    <ee:set-payload><![CDATA[%dw 2.0
output application/json
---
payload]]></ee:set-payload>
</ee:transform>
```

Spring Boot Java:
```java
// 1. Jackson auto-escapes JSON output (safe by default)
@GetMapping("/users/{id}")
public ResponseEntity<UserDTO> getUser(@PathVariable Long id) {
    return ResponseEntity.ok(userService.findById(id)); // JSON auto-escaped
}

// 2. Sanitize input on write
@Service
public class CommentService {
    public CommentDTO create(CreateCommentRequest request) {
        String sanitized = HtmlUtils.htmlEscape(request.getContent());
        Comment comment = new Comment(sanitized);
        return toDTO(repository.save(comment));
    }
}

// 3. Content Security Policy header
@Configuration
public class SecurityHeadersConfig {
    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        return http
            .headers(headers -> headers
                .contentSecurityPolicy(csp -> csp.policyDirectives(
                    "default-src 'self'; script-src 'self'; style-src 'self'"))
                .xssProtection(xss -> xss.headerValue(XXssProtectionHeaderWriter.HeaderValue.ENABLED_MODE_BLOCK)))
            .build();
    }
}
```

Key mapping rules:
- JSON APIs are less vulnerable to XSS (Jackson auto-escapes).
- Sanitize HTML input with HtmlUtils.htmlEscape() or Jsoup.
- Add Content-Security-Policy headers for defense in depth.
- Spring Security adds X-XSS-Protection header by default.""",
    },
    {
        "title": "Security Headers Configuration",
        "category": "security",
        "content": """MuleSoft Response Headers -> Spring Boot Security Headers

MuleSoft XML:
```xml
<flow name="secureFlow">
    <http:listener config-ref="HTTP_Listener" path="/api/data" method="GET">
        <http:response>
            <http:headers><![CDATA[#[{
                'X-Content-Type-Options': 'nosniff',
                'X-Frame-Options': 'DENY',
                'Strict-Transport-Security': 'max-age=31536000; includeSubDomains'
            }]]]></http:headers>
        </http:response>
    </http:listener>
</flow>
```

Spring Boot Java:
```java
@Configuration
@EnableWebSecurity
public class SecurityConfig {
    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        return http
            .headers(headers -> headers
                .contentTypeOptions(Customizer.withDefaults())  // X-Content-Type-Options: nosniff
                .frameOptions(frame -> frame.deny())             // X-Frame-Options: DENY
                .httpStrictTransportSecurity(hsts -> hsts
                    .maxAgeInSeconds(31536000)
                    .includeSubDomains(true))
                .contentSecurityPolicy(csp -> csp
                    .policyDirectives("default-src 'self'"))
                .referrerPolicy(referrer -> referrer
                    .policy(ReferrerPolicyHeaderWriter.ReferrerPolicy.STRICT_ORIGIN_WHEN_CROSS_ORIGIN))
                .permissionsPolicy(perms -> perms
                    .policy("camera=(), microphone=(), geolocation=()")))
            .build();
    }
}
```

Key mapping rules:
- MuleSoft manual response headers map to Spring Security headers() configuration.
- Spring Security adds common security headers by default.
- Additional headers (CSP, Referrer-Policy, Permissions-Policy) configured explicitly.
- HSTS forces HTTPS connections for the specified duration.""",
    },
    # ==================================================================
    #  9. Performance Patterns (15 docs)
    # ==================================================================
    {
        "title": "Connection Pooling HikariCP Tuning",
        "category": "performance",
        "content": """MuleSoft DB Pool -> Spring Boot HikariCP Tuning

MuleSoft XML:
```xml
<db:config name="Database_Config">
    <db:generic-connection url="jdbc:postgresql://localhost:5432/mydb">
        <db:pooling-profile maxPoolSize="30" minPoolSize="10"/>
    </db:generic-connection>
</db:config>
```

Spring Boot application.yml:
```yaml
spring:
  datasource:
    hikari:
      maximum-pool-size: 30
      minimum-idle: 10
      idle-timeout: 300000      # 5 min
      max-lifetime: 1800000     # 30 min
      connection-timeout: 30000  # 30 sec
      validation-timeout: 5000   # 5 sec
      leak-detection-threshold: 60000  # 1 min (dev only)
      pool-name: AppPool
      connection-test-query: SELECT 1
```

Sizing formula:
```java
// Pool size = (core_count * 2) + effective_spindle_count
// For most apps: 10-20 connections is sufficient
// Monitor with Actuator metrics: hikaricp.connections.*
```

Key mapping rules:
- MuleSoft pooling-profile maps to spring.datasource.hikari properties.
- maxPoolSize typically 2x CPU cores for most workloads.
- Enable leak-detection-threshold in development to find connection leaks.
- Monitor pool utilization via /actuator/metrics/hikaricp.connections.active.""",
    },
    {
        "title": "JPA N+1 Query Problem and EntityGraph",
        "category": "performance",
        "content": """MuleSoft JOIN Query -> Spring Boot @EntityGraph to Avoid N+1

MuleSoft XML (single query with JOIN):
```xml
<db:select config-ref="Database_Config">
    <db:sql>SELECT o.*, i.* FROM orders o JOIN order_items i ON o.id = i.order_id</db:sql>
</db:select>
```

Spring Boot Java (N+1 problem):
```java
// BAD - causes N+1 queries
@Entity
public class Order {
    @OneToMany(mappedBy = "order", fetch = FetchType.LAZY)
    private List<OrderItem> items; // Each access triggers a separate query!
}

// When you do: orders.forEach(o -> o.getItems().size()); // N+1 queries!
```

Spring Boot Java (FIXED with @EntityGraph):
```java
public interface OrderRepository extends JpaRepository<Order, Long> {
    @EntityGraph(attributePaths = {"items"})
    List<Order> findAll();

    @EntityGraph(attributePaths = {"items", "customer"})
    @Query("SELECT o FROM Order o WHERE o.status = :status")
    List<Order> findByStatusWithDetails(@Param("status") String status);
}

// Or use JOIN FETCH:
@Query("SELECT DISTINCT o FROM Order o JOIN FETCH o.items WHERE o.status = :status")
List<Order> findByStatusWithItems(@Param("status") String status);
```

Key mapping rules:
- MuleSoft SQL JOINs don't have N+1 problem (raw SQL).
- JPA LAZY loading causes N+1; fix with @EntityGraph or JOIN FETCH.
- @EntityGraph(attributePaths) eager-loads specific associations.
- Use DISTINCT with JOIN FETCH to avoid duplicate parent entities.
- Monitor with spring.jpa.show-sql=true during development.""",
    },
    {
        "title": "Lazy vs Eager Loading Strategy",
        "category": "performance",
        "content": """MuleSoft Query Strategy -> JPA Lazy vs Eager Loading

MuleSoft XML:
```xml
<!-- MuleSoft fetches exactly what SQL returns -->
<db:select config-ref="Database_Config">
    <db:sql>SELECT * FROM orders</db:sql>
</db:select>
<!-- No automatic relationship loading -->
```

Spring Boot Java:
```java
@Entity
public class Order {
    // LAZY (default for collections) - loaded on access
    @OneToMany(mappedBy = "order", fetch = FetchType.LAZY)
    private List<OrderItem> items;

    // EAGER - loaded immediately with parent
    @ManyToOne(fetch = FetchType.EAGER)  // BAD for most cases
    private Customer customer;
}

// BEST PRACTICE: Always LAZY, fetch when needed
@Entity
public class Order {
    @ManyToOne(fetch = FetchType.LAZY)  // GOOD
    private Customer customer;

    @OneToMany(mappedBy = "order", fetch = FetchType.LAZY)  // GOOD (default)
    private List<OrderItem> items;
}

// Load eagerly when needed via @EntityGraph or JOIN FETCH
@EntityGraph(attributePaths = {"customer", "items"})
Optional<Order> findById(Long id);
```

Key mapping rules:
- Always use FetchType.LAZY as default for all relationships.
- Never use FetchType.EAGER on collections (@OneToMany, @ManyToMany).
- Use @EntityGraph or JOIN FETCH to load associations when needed.
- MuleSoft SQL approach is equivalent to lazy + explicit join fetching.""",
    },
    {
        "title": "Query Optimization with Projections",
        "category": "performance",
        "content": """MuleSoft Selective SQL -> Spring Boot DTO Projections

MuleSoft XML:
```xml
<db:select config-ref="Database_Config">
    <db:sql>SELECT id, name, status FROM orders WHERE status = :status</db:sql>
</db:select>
```

Spring Boot Java:
```java
// Interface-based projection (SELECT only needed columns)
public interface OrderSummary {
    Long getId();
    String getName();
    String getStatus();
}

public interface OrderRepository extends JpaRepository<Order, Long> {
    List<OrderSummary> findByStatus(String status); // Only fetches id, name, status
}

// Class-based DTO projection
public record OrderSummaryDTO(Long id, String name, String status) {}

@Query("SELECT new com.example.dto.OrderSummaryDTO(o.id, o.name, o.status) FROM Order o WHERE o.status = :status")
List<OrderSummaryDTO> findSummaryByStatus(@Param("status") String status);

// Native query projection
@Query(value = "SELECT id, name, status FROM orders WHERE status = ?1", nativeQuery = true)
List<OrderSummary> findByStatusNative(String status);
```

Key mapping rules:
- MuleSoft SELECT specific columns maps to JPA projections.
- Interface projections avoid fetching unnecessary columns.
- DTO projections with constructor expressions for computed values.
- Projections reduce memory usage and network transfer.""",
    },
    {
        "title": "Redis Caching Strategy",
        "category": "performance",
        "content": """MuleSoft Object Store Cache -> Spring Boot Redis Caching Strategy

MuleSoft XML:
```xml
<ee:cache cachingStrategy-ref="cacheConfig">
    <db:select config-ref="Database_Config">
        <db:sql>SELECT * FROM products WHERE category = :cat</db:sql>
    </db:select>
</ee:cache>
```

Spring Boot Java:
```java
@Service
@Slf4j
public class ProductService {

    @Cacheable(value = "products", key = "#category", unless = "#result.isEmpty()")
    public List<ProductDTO> findByCategory(String category) {
        log.info("Cache MISS for category: {}", category);
        return repository.findByCategory(category).stream().map(this::toDTO).toList();
    }

    @CachePut(value = "products", key = "#result.category")
    public ProductDTO update(Long id, UpdateProductRequest req) {
        // Updates the cache with the new value
        Product product = repository.findById(id).orElseThrow();
        product.setName(req.getName());
        return toDTO(repository.save(product));
    }

    @CacheEvict(value = "products", allEntries = true)
    @Scheduled(fixedRate = 3600000) // Evict every hour
    public void evictProductCache() {
        log.info("Evicting product cache");
    }
}

@Configuration
@EnableCaching
public class CacheConfig {
    @Bean
    public RedisCacheManager cacheManager(RedisConnectionFactory factory) {
        RedisCacheConfiguration defaultConfig = RedisCacheConfiguration.defaultCacheConfig()
            .entryTtl(Duration.ofMinutes(30))
            .serializeValuesWith(SerializationPair.fromSerializer(new GenericJackson2JsonRedisSerializer()));
        return RedisCacheManager.builder(factory)
            .cacheDefaults(defaultConfig)
            .withCacheConfiguration("products", defaultConfig.entryTtl(Duration.ofHours(1)))
            .build();
    }
}
```

Key mapping rules:
- MuleSoft cache scope maps to @Cacheable annotation.
- Cache config with TTL maps to RedisCacheConfiguration.entryTtl().
- Use @CachePut for write-through and @CacheEvict for invalidation.
- unless attribute prevents caching empty results.""",
    },
    {
        "title": "Response Compression with Gzip",
        "category": "performance",
        "content": """MuleSoft Response Compression -> Spring Boot Gzip Configuration

MuleSoft XML:
```xml
<!-- MuleSoft handles compression at the API gateway level -->
```

Spring Boot application.yml:
```yaml
server:
  compression:
    enabled: true
    mime-types: application/json,application/xml,text/html,text/plain,text/css,application/javascript
    min-response-size: 1024  # Only compress responses > 1KB
```

Spring Boot Java (programmatic):
```java
@Configuration
public class CompressionConfig {
    @Bean
    public FilterRegistrationBean<CompressingFilter> compressionFilter() {
        FilterRegistrationBean<CompressingFilter> registration = new FilterRegistrationBean<>();
        registration.setFilter(new CompressingFilter());
        registration.addUrlPatterns("/api/*");
        registration.setOrder(1);
        return registration;
    }
}
```

Key mapping rules:
- MuleSoft API gateway compression maps to server.compression properties.
- Enable gzip for JSON/XML/HTML responses over 1KB.
- Compression reduces bandwidth by 60-80% for text-based responses.
- Client must send Accept-Encoding: gzip header.""",
    },
    {
        "title": "Async REST Endpoints",
        "category": "performance",
        "content": """MuleSoft Async Processing -> Spring Boot Async Endpoints

MuleSoft XML:
```xml
<flow name="asyncFlow">
    <http:listener config-ref="HTTP_Listener" path="/api/process" method="POST"/>
    <async>
        <flow-ref name="longRunningProcess"/>
    </async>
    <set-payload value='{"status": "accepted", "trackingId": "#[vars.trackingId]"}'/>
</flow>
```

Spring Boot Java:
```java
@RestController
@RequestMapping("/api")
public class ProcessController {

    @PostMapping("/process")
    public ResponseEntity<AcceptedResponse> processAsync(@RequestBody ProcessRequest request) {
        String trackingId = UUID.randomUUID().toString();
        processingService.processAsync(trackingId, request); // fire and forget
        return ResponseEntity.accepted()
            .body(new AcceptedResponse("accepted", trackingId));
    }

    @GetMapping("/process/{trackingId}/status")
    public ResponseEntity<StatusResponse> getStatus(@PathVariable String trackingId) {
        return ResponseEntity.ok(processingService.getStatus(trackingId));
    }
}

@Service
public class ProcessingService {
    @Async
    public void processAsync(String trackingId, ProcessRequest request) {
        updateStatus(trackingId, "PROCESSING");
        // long running work...
        updateStatus(trackingId, "COMPLETED");
    }
}
```

Key mapping rules:
- MuleSoft async scope with immediate response maps to 202 Accepted pattern.
- Return tracking ID for status polling.
- @Async method runs in a separate thread.
- Provide a status endpoint for clients to check progress.""",
    },
    {
        "title": "Reactive WebFlux Basics",
        "category": "performance",
        "content": """MuleSoft Async/Non-Blocking -> Spring WebFlux Reactive

MuleSoft XML:
```xml
<flow name="nonBlockingFlow" processingStrategy="non-blocking">
    <http:listener config-ref="HTTP_Listener" path="/api/data" method="GET"/>
    <http:request config-ref="External_API" path="/v1/data" method="GET"/>
</flow>
```

Spring Boot Java (WebFlux):
```java
@RestController
@RequestMapping("/api")
public class ReactiveController {

    private final WebClient webClient;

    @GetMapping("/data")
    public Mono<DataDTO> getData() {
        return webClient.get().uri("/v1/data")
            .retrieve()
            .bodyToMono(DataDTO.class);
    }

    @GetMapping("/data/stream")
    public Flux<DataDTO> streamData() {
        return webClient.get().uri("/v1/data/stream")
            .retrieve()
            .bodyToFlux(DataDTO.class);
    }

    @GetMapping("/combined")
    public Mono<CombinedDTO> getCombined() {
        Mono<DataDTO> data = webClient.get().uri("/v1/data").retrieve().bodyToMono(DataDTO.class);
        Mono<ConfigDTO> config = webClient.get().uri("/v1/config").retrieve().bodyToMono(ConfigDTO.class);
        return Mono.zip(data, config, CombinedDTO::new);
    }
}
```

Key mapping rules:
- MuleSoft non-blocking processing maps to Spring WebFlux reactive streams.
- Return Mono<T> for single values, Flux<T> for collections/streams.
- WebFlux uses fewer threads for the same throughput (event-loop model).
- Use Mono.zip() for parallel non-blocking calls (like scatter-gather).""",
    },
    {
        "title": "Database Indexing Strategies",
        "category": "performance",
        "content": """MuleSoft Query Optimization -> Database Indexing in Spring Boot

MuleSoft XML:
```xml
<db:select config-ref="Database_Config">
    <db:sql>SELECT * FROM orders WHERE customer_id = :custId AND status = :status ORDER BY created_at DESC</db:sql>
</db:select>
```

Spring Boot Java + Flyway:
```sql
-- V3__add_performance_indexes.sql
CREATE INDEX idx_orders_customer_status ON orders(customer_id, status);
CREATE INDEX idx_orders_created_at ON orders(created_at DESC);
CREATE INDEX idx_orders_customer_created ON orders(customer_id, created_at DESC);

-- Partial index for common queries
CREATE INDEX idx_orders_active ON orders(customer_id) WHERE status = 'ACTIVE';

-- Text search index
CREATE INDEX idx_products_name_gin ON products USING gin(to_tsvector('english', name));
```

JPA Entity annotations:
```java
@Entity
@Table(name = "orders", indexes = {
    @Index(name = "idx_orders_customer_status", columnList = "customer_id, status"),
    @Index(name = "idx_orders_created_at", columnList = "created_at DESC")
})
public class Order {
    @Column(name = "customer_id")
    private Long customerId;
    private String status;
    private LocalDateTime createdAt;
}
```

Key mapping rules:
- Create indexes for columns used in WHERE, JOIN, and ORDER BY clauses.
- Composite indexes for multi-column queries (order matters).
- Use EXPLAIN ANALYZE to verify query plans.
- Prefer Flyway migrations for index management over JPA auto-generation.""",
    },
    {
        "title": "Bulk Operations Optimization",
        "category": "performance",
        "content": """MuleSoft Batch/Bulk -> Spring Boot Bulk Optimization

MuleSoft XML:
```xml
<batch:job name="bulkImport">
    <batch:process-records>
        <batch:step name="loadStep">
            <db:bulk-insert config-ref="Database_Config">
                <db:sql>INSERT INTO products (name, price) VALUES (:name, :price)</db:sql>
            </db:bulk-insert>
        </batch:step>
    </batch:process-records>
</batch:job>
```

Spring Boot Java:
```java
@Service
@Transactional
public class BulkImportService {

    // JPA batch insert (configure hibernate.jdbc.batch_size)
    public void bulkInsert(List<Product> products) {
        for (int i = 0; i < products.size(); i++) {
            entityManager.persist(products.get(i));
            if (i % 50 == 0) {
                entityManager.flush();
                entityManager.clear(); // Free memory
            }
        }
    }

    // JdbcTemplate batch (faster for raw inserts)
    public void bulkInsertJdbc(List<Product> products) {
        jdbcTemplate.batchUpdate(
            "INSERT INTO products (name, price) VALUES (?, ?)",
            new BatchPreparedStatementSetter() {
                @Override public void setValues(PreparedStatement ps, int i) throws SQLException {
                    ps.setString(1, products.get(i).getName());
                    ps.setBigDecimal(2, products.get(i).getPrice());
                }
                @Override public int getBatchSize() { return products.size(); }
            });
    }
}
```

Key mapping rules:
- MuleSoft db:bulk-insert maps to JdbcTemplate.batchUpdate() for best performance.
- JPA batch insert needs flush/clear every N records to manage memory.
- Configure hibernate.jdbc.batch_size=50 and order_inserts=true.
- JdbcTemplate batch is 2-5x faster than JPA for large imports.""",
    },
    {
        "title": "HTTP Client Connection Pooling",
        "category": "performance",
        "content": """MuleSoft HTTP Request Pool -> Spring Boot WebClient Connection Pool

MuleSoft XML:
```xml
<http:request-config name="External_API">
    <http:request-connection host="api.example.com" port="443" protocol="HTTPS">
        <http:client-socket-properties connectionIdleTimeout="30000"/>
    </http:request-connection>
</http:request-config>
```

Spring Boot Java:
```java
@Configuration
public class WebClientConfig {
    @Bean
    public WebClient webClient() {
        ConnectionProvider provider = ConnectionProvider.builder("custom")
            .maxConnections(50)
            .maxIdleTime(Duration.ofSeconds(30))
            .maxLifeTime(Duration.ofMinutes(5))
            .pendingAcquireTimeout(Duration.ofSeconds(10))
            .evictInBackground(Duration.ofSeconds(60))
            .build();

        HttpClient httpClient = HttpClient.create(provider)
            .responseTimeout(Duration.ofSeconds(10))
            .option(ChannelOption.CONNECT_TIMEOUT_MILLIS, 5000);

        return WebClient.builder()
            .clientConnector(new ReactorClientHttpConnector(httpClient))
            .baseUrl("https://api.example.com")
            .build();
    }
}
```

Key mapping rules:
- MuleSoft HTTP connection pool maps to Reactor Netty ConnectionProvider.
- maxConnections limits concurrent connections to the target.
- maxIdleTime matches connectionIdleTimeout.
- Configure per-host limits with .forRemoteHost() for multiple targets.
- Reuse WebClient instances; create once as a @Bean.""",
    },
    {
        "title": "Thread Pool Configuration",
        "category": "performance",
        "content": """MuleSoft Threading Profile -> Spring Boot Thread Pool Config

MuleSoft XML:
```xml
<flow name="highThroughputFlow" processingStrategy="queued-asynchronous">
    <threading-profile maxThreadsActive="50" maxThreadsIdle="10" poolExhaustedAction="WAIT"/>
</flow>
```

Spring Boot Java:
```java
@Configuration
@EnableAsync
public class ThreadPoolConfig {

    @Bean("taskExecutor")
    public Executor taskExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(10);
        executor.setMaxPoolSize(50);
        executor.setQueueCapacity(100);
        executor.setKeepAliveSeconds(60);
        executor.setThreadNamePrefix("app-async-");
        executor.setRejectedExecutionHandler(new ThreadPoolExecutor.CallerRunsPolicy());
        executor.initialize();
        return executor;
    }

    @Bean("ioExecutor")
    public Executor ioExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(20);
        executor.setMaxPoolSize(100);
        executor.setQueueCapacity(500);
        executor.setThreadNamePrefix("io-");
        executor.initialize();
        return executor;
    }
}

// Usage:
@Async("ioExecutor")
public CompletableFuture<DataDTO> fetchExternalData() { ... }
```

Key mapping rules:
- MuleSoft threading-profile maps to ThreadPoolTaskExecutor @Bean.
- maxThreadsActive maps to maxPoolSize.
- poolExhaustedAction WAIT maps to CallerRunsPolicy.
- Create separate pools for CPU-bound and IO-bound tasks.
- Name threads for easier debugging with setThreadNamePrefix.""",
    },
    {
        "title": "Monitoring with Micrometer",
        "category": "performance",
        "content": """MuleSoft Analytics -> Spring Boot Micrometer Metrics

MuleSoft XML:
```xml
<!-- MuleSoft uses Anypoint Monitoring -->
<flow name="monitoredFlow">
    <logger level="INFO" message="Processing request"/>
</flow>
```

Spring Boot Java:
```java
@Service
@Slf4j
public class OrderService {
    private final MeterRegistry meterRegistry;
    private final Counter orderCounter;
    private final Timer orderTimer;

    public OrderService(MeterRegistry meterRegistry) {
        this.meterRegistry = meterRegistry;
        this.orderCounter = Counter.builder("orders.created").tag("type", "api").register(meterRegistry);
        this.orderTimer = Timer.builder("orders.processing.time").register(meterRegistry);
    }

    public OrderDTO createOrder(CreateOrderRequest request) {
        return orderTimer.record(() -> {
            OrderDTO order = doCreate(request);
            orderCounter.increment();
            meterRegistry.gauge("orders.pending", orderRepository.countByStatus("PENDING"));
            return order;
        });
    }
}
```

application.yml:
```yaml
management:
  metrics:
    export:
      prometheus:
        enabled: true
  endpoints:
    web:
      exposure:
        include: health,info,metrics,prometheus
```

Key mapping rules:
- MuleSoft Anypoint Monitoring maps to Micrometer + Prometheus/Grafana.
- Counter for counting events (orders created, errors).
- Timer for measuring duration (request processing time).
- Gauge for current values (pending orders, pool size).
- Metrics exposed at /actuator/prometheus for scraping.""",
    },
    {
        "title": "JVM Tuning Basics",
        "category": "performance",
        "content": """MuleSoft JVM Settings -> Spring Boot JVM Tuning

MuleSoft wrapper.conf:
```properties
wrapper.java.maxmemory=2048
wrapper.java.additional.4=-XX:+UseG1GC
```

Spring Boot Dockerfile / startup:
```dockerfile
FROM eclipse-temurin:17-jre-jammy
COPY target/app.jar app.jar
ENTRYPOINT ["java", \
    "-Xms512m", \
    "-Xmx2g", \
    "-XX:+UseG1GC", \
    "-XX:MaxGCPauseMillis=200", \
    "-XX:+UseStringDeduplication", \
    "-XX:+HeapDumpOnOutOfMemoryError", \
    "-XX:HeapDumpPath=/tmp/heapdump.hprof", \
    "-Djava.security.egd=file:/dev/./urandom", \
    "-jar", "app.jar"]
```

Spring Boot application.yml:
```yaml
server:
  tomcat:
    threads:
      max: 200
      min-spare: 20
    max-connections: 10000
    accept-count: 100
```

Key mapping rules:
- MuleSoft JVM settings map to JAVA_OPTS in Spring Boot.
- Use G1GC for most workloads; ZGC for ultra-low latency.
- Set -Xms and -Xmx to same value in containers (avoid resize overhead).
- Enable HeapDumpOnOutOfMemoryError for production debugging.
- Configure Tomcat threads for expected concurrent load.""",
    },
    # ==================================================================
    #  10. API Design Patterns (15 docs)
    # ==================================================================
    {
        "title": "RESTful URL Design Conventions",
        "category": "api-patterns",
        "content": """MuleSoft API Path Design -> Spring Boot RESTful URL Conventions

MuleSoft XML:
```xml
<http:listener path="/api/orders" method="GET"/>
<http:listener path="/api/orders/{orderId}" method="GET"/>
<http:listener path="/api/orders/{orderId}/items" method="GET"/>
<http:listener path="/api/orders/{orderId}/items/{itemId}" method="GET"/>
```

Spring Boot Java:
```java
@RestController
@RequestMapping("/api")
public class OrderController {
    @GetMapping("/orders")                              // List orders
    @PostMapping("/orders")                             // Create order
    @GetMapping("/orders/{orderId}")                    // Get one order
    @PutMapping("/orders/{orderId}")                    // Replace order
    @PatchMapping("/orders/{orderId}")                  // Partial update
    @DeleteMapping("/orders/{orderId}")                 // Delete order
    @GetMapping("/orders/{orderId}/items")              // List items of order
    @PostMapping("/orders/{orderId}/items")             // Add item to order
    @GetMapping("/orders/{orderId}/items/{itemId}")     // Get specific item
}
```

URL conventions:
```
/api/resources              -> collection (plural nouns)
/api/resources/{id}         -> single resource
/api/resources/{id}/sub     -> sub-resource collection
/api/resources/{id}/sub/{subId} -> specific sub-resource
/api/resources?status=active&page=0&size=20 -> filtering/pagination
```

Key mapping rules:
- Use plural nouns for resources (orders, not order).
- Use path parameters for resource identity.
- Use query parameters for filtering, sorting, pagination.
- Nest sub-resources under parent: /orders/{id}/items.
- Avoid verbs in URLs; use HTTP methods instead.""",
    },
    {
        "title": "HTTP Method Semantics",
        "category": "api-patterns",
        "content": """MuleSoft HTTP Methods -> Spring Boot Method Semantics

MuleSoft XML:
```xml
<http:listener path="/api/orders" method="GET"/>    <!-- Safe, idempotent -->
<http:listener path="/api/orders" method="POST"/>   <!-- Not safe, not idempotent -->
<http:listener path="/api/orders/{id}" method="PUT"/>   <!-- Idempotent -->
<http:listener path="/api/orders/{id}" method="PATCH"/> <!-- Not idempotent -->
<http:listener path="/api/orders/{id}" method="DELETE"/><!-- Idempotent -->
```

Spring Boot Java:
```java
@RestController
@RequestMapping("/api/orders")
public class OrderController {

    @GetMapping           // GET: Read-only, cacheable, safe
    public ResponseEntity<Page<OrderDTO>> list(Pageable pageable) { ... }

    @PostMapping          // POST: Create new resource, returns 201
    public ResponseEntity<OrderDTO> create(@Valid @RequestBody CreateOrderRequest req) { ... }

    @PutMapping("/{id}")  // PUT: Full replacement, idempotent
    public ResponseEntity<OrderDTO> replace(@PathVariable Long id, @Valid @RequestBody OrderDTO order) { ... }

    @PatchMapping("/{id}")// PATCH: Partial update
    public ResponseEntity<OrderDTO> update(@PathVariable Long id, @RequestBody Map<String, Object> updates) { ... }

    @DeleteMapping("/{id}")// DELETE: Remove, idempotent
    public ResponseEntity<Void> delete(@PathVariable Long id) { ... }
}
```

Key mapping rules:
- GET: retrieve, never modify state. Safe and cacheable.
- POST: create new resource. Return 201 with Location header.
- PUT: full replacement (client sends complete resource). Idempotent.
- PATCH: partial update (client sends only changed fields).
- DELETE: remove resource. Return 204 No Content. Idempotent.""",
    },
    {
        "title": "HTTP Status Code Usage Guide",
        "category": "api-patterns",
        "content": """MuleSoft HTTP Status -> Spring Boot Status Code Guide

MuleSoft XML:
```xml
<set-variable variableName="httpStatus" value="200"/>
<set-variable variableName="httpStatus" value="201"/>
<set-variable variableName="httpStatus" value="404"/>
```

Spring Boot Java:
```java
// 2xx Success
ResponseEntity.ok(body);                          // 200 OK
ResponseEntity.created(location).body(body);       // 201 Created
ResponseEntity.accepted().body(body);              // 202 Accepted (async)
ResponseEntity.noContent().build();                // 204 No Content (delete)

// 4xx Client Errors
ResponseEntity.badRequest().body(error);           // 400 Bad Request
ResponseEntity.status(HttpStatus.UNAUTHORIZED);    // 401 Unauthorized
ResponseEntity.status(HttpStatus.FORBIDDEN);       // 403 Forbidden
ResponseEntity.notFound().build();                 // 404 Not Found
ResponseEntity.status(HttpStatus.CONFLICT);        // 409 Conflict
ResponseEntity.unprocessableEntity().body(error);  // 422 Unprocessable
ResponseEntity.status(HttpStatus.TOO_MANY_REQUESTS);// 429 Rate Limited

// 5xx Server Errors
ResponseEntity.internalServerError().body(error);  // 500 Internal Error
ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE); // 503 Unavailable
```

Key mapping rules:
- 200: successful GET, PUT, PATCH
- 201: successful POST (resource created)
- 204: successful DELETE (no body)
- 400: validation errors, malformed request
- 401: missing or invalid authentication
- 403: authenticated but not authorized
- 404: resource not found
- 409: conflict (duplicate, version mismatch)
- 422: business rule violation
- 429: rate limit exceeded
- 500: unexpected server error
- 503: downstream service unavailable""",
    },
    {
        "title": "Request Response DTO Design",
        "category": "api-patterns",
        "content": """MuleSoft Payload Design -> Spring Boot DTO Design Pattern

MuleSoft XML:
```xml
<ee:transform>
    <ee:set-payload><![CDATA[%dw 2.0
output application/json
---
{request: {name: payload.name}, response: {id: vars.id, name: vars.name, createdAt: now()}}]]></ee:set-payload>
</ee:transform>
```

Spring Boot Java:
```java
// Request DTO (input validation)
public class CreateOrderRequest {
    @NotNull private Long customerId;
    @NotEmpty private List<OrderItemRequest> items;
    private String notes;
}

public class OrderItemRequest {
    @NotNull private Long productId;
    @Positive private int quantity;
}

// Response DTO (output formatting)
public record OrderResponse(
    Long id,
    String status,
    String customerName,
    List<OrderItemResponse> items,
    BigDecimal totalAmount,
    LocalDateTime createdAt
) {}

public record OrderItemResponse(
    Long productId,
    String productName,
    int quantity,
    BigDecimal unitPrice,
    BigDecimal lineTotal
) {}

// List response wrapper
public record PagedResponse<T>(
    List<T> content,
    long totalElements,
    int totalPages,
    int page,
    int size
) {}
```

Key mapping rules:
- Separate request DTOs (with validation) from response DTOs.
- Request DTOs use mutable classes with setters for Jackson deserialization.
- Response DTOs use Java Records for immutability.
- Never expose JPA entities in API responses.
- Include only fields the client needs in response DTOs.""",
    },
    {
        "title": "Pagination Response Format",
        "category": "api-patterns",
        "content": """MuleSoft Paged Response -> Spring Boot Pagination Format

MuleSoft XML:
```xml
<ee:transform>
    <ee:set-payload><![CDATA[%dw 2.0
output application/json
---
{
    data: payload,
    pagination: {
        page: vars.page,
        size: vars.size,
        total: vars.totalCount
    }
}]]></ee:set-payload>
</ee:transform>
```

Spring Boot Java:
```java
@GetMapping("/orders")
public ResponseEntity<Page<OrderDTO>> getOrders(
        @RequestParam(defaultValue = "0") int page,
        @RequestParam(defaultValue = "20") int size) {
    Page<OrderDTO> result = orderService.findAll(PageRequest.of(page, size));
    return ResponseEntity.ok(result);
}

// Custom paged response:
public record PagedResponse<T>(
    List<T> data,
    PaginationMeta pagination
) {
    public static <T> PagedResponse<T> from(Page<T> page) {
        return new PagedResponse<>(page.getContent(),
            new PaginationMeta(page.getNumber(), page.getSize(),
                page.getTotalElements(), page.getTotalPages()));
    }
}

public record PaginationMeta(int page, int size, long totalElements, int totalPages) {}
```

Response JSON:
```json
{
    "data": [...],
    "pagination": {
        "page": 0,
        "size": 20,
        "totalElements": 150,
        "totalPages": 8
    }
}
```

Key mapping rules:
- MuleSoft manual pagination response maps to Spring Data Page or custom wrapper.
- Include page number, size, total elements, and total pages.
- Use Spring Data Page<T> for standard format.
- Use custom PagedResponse for different JSON structure.""",
    },
    {
        "title": "Error Response Format RFC 7807",
        "category": "api-patterns",
        "content": """MuleSoft Error Response -> Spring Boot RFC 7807 Problem Details

MuleSoft XML:
```xml
<on-error-propagate>
    <ee:transform>
        <ee:set-payload><![CDATA[%dw 2.0
output application/json
---
{error: "Not Found", message: error.description, status: 404}]]></ee:set-payload>
    </ee:transform>
</on-error-propagate>
```

Spring Boot Java (RFC 7807):
```java
@ControllerAdvice
public class ProblemDetailExceptionHandler {

    @ExceptionHandler(ResourceNotFoundException.class)
    public ProblemDetail handleNotFound(ResourceNotFoundException ex, HttpServletRequest request) {
        ProblemDetail problem = ProblemDetail.forStatusAndDetail(HttpStatus.NOT_FOUND, ex.getMessage());
        problem.setTitle("Resource Not Found");
        problem.setType(URI.create("https://api.example.com/errors/not-found"));
        problem.setInstance(URI.create(request.getRequestURI()));
        problem.setProperty("timestamp", Instant.now());
        return problem;
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ProblemDetail handleValidation(MethodArgumentNotValidException ex) {
        ProblemDetail problem = ProblemDetail.forStatus(HttpStatus.BAD_REQUEST);
        problem.setTitle("Validation Failed");
        List<String> errors = ex.getBindingResult().getFieldErrors().stream()
            .map(e -> e.getField() + ": " + e.getDefaultMessage()).toList();
        problem.setProperty("errors", errors);
        return problem;
    }
}
```

Response JSON (RFC 7807):
```json
{
    "type": "https://api.example.com/errors/not-found",
    "title": "Resource Not Found",
    "status": 404,
    "detail": "Order not found with id: 123",
    "instance": "/api/orders/123",
    "timestamp": "2024-01-15T10:30:00Z"
}
```

Key mapping rules:
- MuleSoft custom error payloads map to Spring Boot 6 ProblemDetail (RFC 7807).
- ProblemDetail is built-in to Spring Boot 3+.
- Include type (error category URI), title, status, detail, and instance.
- Custom properties added via setProperty() for extra context.""",
    },
    {
        "title": "API Versioning URL vs Header",
        "category": "api-patterns",
        "content": """MuleSoft API Versioning -> Spring Boot Versioning Strategies

MuleSoft XML:
```xml
<http:listener path="/api/v1/orders" method="GET"/>
<http:listener path="/api/v2/orders" method="GET"/>
```

Spring Boot Java (URL versioning):
```java
@RestController
@RequestMapping("/api/v1/orders")
public class OrderControllerV1 {
    @GetMapping
    public List<OrderV1DTO> getOrders() { return service.findAllV1(); }
}

@RestController
@RequestMapping("/api/v2/orders")
public class OrderControllerV2 {
    @GetMapping
    public List<OrderV2DTO> getOrders() { return service.findAllV2(); }
}
```

Spring Boot Java (Header versioning):
```java
@RestController
@RequestMapping("/api/orders")
public class OrderController {
    @GetMapping(headers = "X-API-Version=1")
    public List<OrderV1DTO> getOrdersV1() { ... }

    @GetMapping(headers = "X-API-Version=2")
    public List<OrderV2DTO> getOrdersV2() { ... }
}
```

Spring Boot Java (Media type versioning):
```java
@GetMapping(produces = "application/vnd.example.v1+json")
public List<OrderV1DTO> getOrdersV1() { ... }

@GetMapping(produces = "application/vnd.example.v2+json")
public List<OrderV2DTO> getOrdersV2() { ... }
```

Key mapping rules:
- URL versioning (/v1/, /v2/) is most common and explicit.
- Header versioning keeps URLs clean but harder to test.
- Media type versioning follows strict REST but is complex.
- Recommend URL versioning for most migration projects.""",
    },
    {
        "title": "Content Negotiation",
        "category": "api-patterns",
        "content": """MuleSoft Content Type -> Spring Boot Content Negotiation

MuleSoft XML:
```xml
<choice>
    <when expression="#[attributes.headers.Accept contains 'xml']">
        <ee:transform><ee:set-payload><![CDATA[output application/xml --- payload]]></ee:set-payload></ee:transform>
    </when>
    <otherwise>
        <ee:transform><ee:set-payload><![CDATA[output application/json --- payload]]></ee:set-payload></ee:transform>
    </otherwise>
</choice>
```

Spring Boot Java:
```java
@GetMapping(value = "/orders", produces = {MediaType.APPLICATION_JSON_VALUE, MediaType.APPLICATION_XML_VALUE})
public List<OrderDTO> getOrders() {
    return orderService.findAll(); // Auto-negotiated based on Accept header
}
```

application.yml:
```yaml
spring:
  mvc:
    contentnegotiation:
      favor-parameter: true
      parameter-name: format
```

pom.xml (for XML):
```xml
<dependency>
    <groupId>com.fasterxml.jackson.dataformat</groupId>
    <artifactId>jackson-dataformat-xml</artifactId>
</dependency>
```

Key mapping rules:
- MuleSoft choice on Accept header is automatic in Spring Boot.
- produces attribute lists supported media types.
- Spring auto-selects format based on Accept header.
- Add jackson-dataformat-xml for XML support.
- Can also negotiate via URL parameter: /orders?format=xml.""",
    },
    {
        "title": "HATEOAS Implementation",
        "category": "api-patterns",
        "content": """MuleSoft Links in Response -> Spring Boot HATEOAS

MuleSoft XML:
```xml
<ee:transform>
    <ee:set-payload><![CDATA[%dw 2.0
output application/json
---
{
    id: payload.id,
    name: payload.name,
    _links: {
        self: {href: "/api/orders/" ++ payload.id},
        items: {href: "/api/orders/" ++ payload.id ++ "/items"},
        customer: {href: "/api/customers/" ++ payload.customerId}
    }
}]]></ee:set-payload>
</ee:transform>
```

Spring Boot Java:
```java
@RestController
@RequestMapping("/api/orders")
public class OrderController {
    @GetMapping("/{id}")
    public EntityModel<OrderDTO> getOrder(@PathVariable Long id) {
        OrderDTO order = orderService.findById(id);
        return EntityModel.of(order,
            linkTo(methodOn(OrderController.class).getOrder(id)).withSelfRel(),
            linkTo(methodOn(OrderController.class).getOrderItems(id)).withRel("items"),
            linkTo(methodOn(CustomerController.class).getCustomer(order.getCustomerId())).withRel("customer"));
    }

    @GetMapping
    public CollectionModel<EntityModel<OrderDTO>> getAllOrders() {
        List<EntityModel<OrderDTO>> orders = orderService.findAll().stream()
            .map(o -> EntityModel.of(o,
                linkTo(methodOn(OrderController.class).getOrder(o.getId())).withSelfRel()))
            .toList();
        return CollectionModel.of(orders,
            linkTo(methodOn(OrderController.class).getAllOrders()).withSelfRel());
    }
}
```

Key mapping rules:
- MuleSoft manual _links maps to Spring HATEOAS EntityModel + linkTo().
- EntityModel wraps DTOs with hypermedia links.
- CollectionModel for list responses with links.
- Use methodOn() for type-safe link generation.""",
    },
    {
        "title": "GraphQL with Spring Boot",
        "category": "api-patterns",
        "content": """MuleSoft REST API -> Spring Boot GraphQL Alternative

MuleSoft XML (multiple REST endpoints):
```xml
<flow name="getOrderWithDetails">
    <http:listener path="/api/orders/{id}" method="GET"/>
    <!-- Fetches order + items + customer in one response -->
</flow>
```

Spring Boot Java (GraphQL):
```java
// schema.graphqls
// type Query { orderById(id: ID!): Order }
// type Order { id: ID!, status: String!, items: [OrderItem!]!, customer: Customer! }
// type OrderItem { id: ID!, productName: String!, quantity: Int!, price: Float! }
// type Customer { id: ID!, name: String!, email: String! }

@Controller
public class OrderGraphQLController {
    @QueryMapping
    public Order orderById(@Argument Long id) {
        return orderService.findById(id);
    }

    @SchemaMapping(typeName = "Order", field = "items")
    public List<OrderItem> items(Order order) {
        return orderItemService.findByOrderId(order.getId());
    }

    @SchemaMapping(typeName = "Order", field = "customer")
    public Customer customer(Order order) {
        return customerService.findById(order.getCustomerId());
    }
}
```

pom.xml:
```xml
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-graphql</artifactId>
</dependency>
```

Key mapping rules:
- Multiple MuleSoft REST endpoints can be consolidated into GraphQL queries.
- GraphQL lets clients request exactly the fields they need.
- @QueryMapping for top-level queries; @SchemaMapping for nested resolvers.
- Accessible at /graphql endpoint with GraphiQL UI at /graphiql.""",
    },
    {
        "title": "Server-Sent Events SSE",
        "category": "api-patterns",
        "content": """MuleSoft Streaming -> Spring Boot Server-Sent Events

MuleSoft XML:
```xml
<flow name="streamUpdates">
    <http:listener config-ref="HTTP_Listener" path="/api/stream" method="GET">
        <http:response>
            <http:headers><![CDATA[#[{'Content-Type': 'text/event-stream'}]]]></http:headers>
        </http:response>
    </http:listener>
</flow>
```

Spring Boot Java:
```java
@RestController
@RequestMapping("/api")
public class StreamController {

    @GetMapping(value = "/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public Flux<ServerSentEvent<OrderUpdateDTO>> streamOrderUpdates() {
        return Flux.interval(Duration.ofSeconds(1))
            .map(seq -> ServerSentEvent.<OrderUpdateDTO>builder()
                .id(String.valueOf(seq))
                .event("order-update")
                .data(orderService.getLatestUpdate())
                .build());
    }

    // Or with SseEmitter (non-reactive):
    @GetMapping("/stream-mvc")
    public SseEmitter streamWithMvc() {
        SseEmitter emitter = new SseEmitter(Long.MAX_VALUE);
        executor.execute(() -> {
            try {
                while (!emitter.isComplete()) {
                    emitter.send(SseEmitter.event()
                        .name("order-update")
                        .data(orderService.getLatestUpdate()));
                    Thread.sleep(1000);
                }
            } catch (Exception e) { emitter.completeWithError(e); }
        });
        return emitter;
    }
}
```

Key mapping rules:
- MuleSoft streaming response maps to Spring SSE with text/event-stream.
- WebFlux: use Flux<ServerSentEvent<T>> for reactive streaming.
- WebMvc: use SseEmitter for servlet-based streaming.
- SSE is simpler than WebSocket for server-to-client push.""",
    },
    {
        "title": "File Download Endpoint",
        "category": "api-patterns",
        "content": """MuleSoft File Response -> Spring Boot File Download

MuleSoft XML:
```xml
<flow name="downloadFileFlow">
    <http:listener config-ref="HTTP_Listener" path="/api/files/{fileName}" method="GET"/>
    <file:read config-ref="File_Config" path="#[attributes.uriParams.fileName]"/>
    <set-variable variableName="contentType" value="application/octet-stream"/>
</flow>
```

Spring Boot Java:
```java
@GetMapping("/files/{fileName}")
public ResponseEntity<Resource> downloadFile(@PathVariable String fileName) {
    Resource resource = fileStorageService.loadAsResource(fileName);
    String contentType = determineContentType(fileName);
    return ResponseEntity.ok()
        .contentType(MediaType.parseMediaType(contentType))
        .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"" + resource.getFilename() + "\"")
        .body(resource);
}

@GetMapping("/reports/{id}/pdf")
public ResponseEntity<byte[]> downloadPdf(@PathVariable Long id) {
    byte[] pdf = reportService.generatePdf(id);
    return ResponseEntity.ok()
        .contentType(MediaType.APPLICATION_PDF)
        .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"report-" + id + ".pdf\"")
        .body(pdf);
}
```

Key mapping rules:
- MuleSoft file:read response maps to Spring Resource or byte[].
- Set Content-Disposition header for download filename.
- Use InputStreamResource for large files to avoid memory issues.
- Determine Content-Type from file extension or stored metadata.""",
    },
    {
        "title": "Multipart Upload Endpoint",
        "category": "api-patterns",
        "content": """MuleSoft Multipart Upload -> Spring Boot Multipart Endpoint

MuleSoft XML:
```xml
<flow name="multipartUploadFlow">
    <http:listener config-ref="HTTP_Listener" path="/api/documents" method="POST"/>
    <set-variable variableName="file" value="#[payload.parts.file]"/>
    <set-variable variableName="title" value="#[payload.parts.title.content]"/>
    <set-variable variableName="description" value="#[payload.parts.description.content]"/>
</flow>
```

Spring Boot Java:
```java
@PostMapping(value = "/documents", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
public ResponseEntity<DocumentDTO> uploadDocument(
        @RequestParam("file") MultipartFile file,
        @RequestParam("title") String title,
        @RequestParam(value = "description", required = false) String description) {
    DocumentDTO doc = documentService.create(file, title, description);
    URI location = ServletUriComponentsBuilder.fromCurrentRequest()
        .path("/{id}").buildAndExpand(doc.getId()).toUri();
    return ResponseEntity.created(location).body(doc);
}
```

Key mapping rules:
- MuleSoft payload.parts.file maps to @RequestParam MultipartFile.
- Text form fields map to @RequestParam String parameters.
- Configure spring.servlet.multipart.max-file-size in YAML.
- Return 201 Created with Location header after upload.""",
    },
    {
        "title": "Idempotency Patterns",
        "category": "api-patterns",
        "content": """MuleSoft Idempotent Message Validator -> Spring Boot Idempotency

MuleSoft XML:
```xml
<idempotent-message-validator idExpression="#[payload.transactionId]" objectStore="idempotentStore"/>
```

Spring Boot Java:
```java
@Service
public class IdempotencyService {
    private final StringRedisTemplate redisTemplate;

    public boolean isProcessed(String idempotencyKey) {
        return Boolean.TRUE.equals(redisTemplate.hasKey("idempotent:" + idempotencyKey));
    }

    public void markProcessed(String idempotencyKey, String result, Duration ttl) {
        redisTemplate.opsForValue().set("idempotent:" + idempotencyKey, result, ttl);
    }
}

@RestController
public class PaymentController {
    @PostMapping("/payments")
    public ResponseEntity<PaymentResult> processPayment(
            @RequestHeader("Idempotency-Key") String idempotencyKey,
            @Valid @RequestBody PaymentRequest request) {
        if (idempotencyService.isProcessed(idempotencyKey)) {
            String cached = idempotencyService.getResult(idempotencyKey);
            return ResponseEntity.ok(objectMapper.readValue(cached, PaymentResult.class));
        }
        PaymentResult result = paymentService.process(request);
        idempotencyService.markProcessed(idempotencyKey, objectMapper.writeValueAsString(result), Duration.ofHours(24));
        return ResponseEntity.status(HttpStatus.CREATED).body(result);
    }
}
```

Key mapping rules:
- MuleSoft idempotent-message-validator maps to Redis-based deduplication.
- Use Idempotency-Key request header for client-provided keys.
- Store results in Redis with TTL for cache expiration.
- Return cached result for duplicate requests (same key).""",
    },
    # ==================================================================
    #  11. MuleSoft Flow Patterns (20 docs)
    # ==================================================================
    {
        "title": "Choice Router to if-else or switch",
        "category": "mulesoft",
        "content": """MuleSoft Choice Router -> Spring Boot if/else or switch

MuleSoft XML:
```xml
<flow name="routeByStatusFlow">
    <choice>
        <when expression="#[payload.status == 'NEW']">
            <flow-ref name="processNewOrder"/>
        </when>
        <when expression="#[payload.status == 'PROCESSING']">
            <flow-ref name="processActiveOrder"/>
        </when>
        <when expression="#[payload.status == 'SHIPPED']">
            <flow-ref name="processShippedOrder"/>
        </when>
        <otherwise>
            <flow-ref name="handleUnknownStatus"/>
        </otherwise>
    </choice>
</flow>
```

Spring Boot Java:
```java
@Service
public class OrderRouter {
    public OrderResult route(Order order) {
        return switch (order.getStatus()) {
            case "NEW" -> processNewOrder(order);
            case "PROCESSING" -> processActiveOrder(order);
            case "SHIPPED" -> processShippedOrder(order);
            default -> handleUnknownStatus(order);
        };
    }
}
```

Key mapping rules:
- MuleSoft choice router maps to Java switch expression or if/else chain.
- Each when clause maps to a case in switch or an if branch.
- otherwise maps to the default case.
- For complex routing, consider the Strategy pattern with a Map of handlers.""",
    },
    {
        "title": "Scatter-Gather to CompletableFuture.allOf",
        "category": "mulesoft",
        "content": """MuleSoft Scatter-Gather -> Spring Boot CompletableFuture.allOf

MuleSoft XML:
```xml
<flow name="aggregateDataFlow">
    <scatter-gather>
        <route>
            <http:request config-ref="Orders_API" path="/v1/orders" method="GET"/>
        </route>
        <route>
            <http:request config-ref="Products_API" path="/v1/products" method="GET"/>
        </route>
        <route>
            <http:request config-ref="Customers_API" path="/v1/customers" method="GET"/>
        </route>
    </scatter-gather>
    <ee:transform>
        <ee:set-payload><![CDATA[%dw 2.0
output application/json
---
{orders: payload[0], products: payload[1], customers: payload[2]}]]></ee:set-payload>
    </ee:transform>
</flow>
```

Spring Boot Java:
```java
@Service
public class AggregationService {
    private final OrderApiClient orderClient;
    private final ProductApiClient productClient;
    private final CustomerApiClient customerClient;

    public AggregatedData aggregate() {
        CompletableFuture<List<OrderDTO>> orders = CompletableFuture.supplyAsync(orderClient::getAll);
        CompletableFuture<List<ProductDTO>> products = CompletableFuture.supplyAsync(productClient::getAll);
        CompletableFuture<List<CustomerDTO>> customers = CompletableFuture.supplyAsync(customerClient::getAll);

        CompletableFuture.allOf(orders, products, customers).join();

        return new AggregatedData(orders.join(), products.join(), customers.join());
    }
}
```

Key mapping rules:
- MuleSoft scatter-gather maps to CompletableFuture.allOf() for parallel execution.
- Each route becomes a CompletableFuture.supplyAsync() call.
- Results are aggregated after all futures complete with .join().
- For WebFlux, use Mono.zip() for the same pattern.""",
    },
    {
        "title": "First Successful Pattern",
        "category": "mulesoft",
        "content": """MuleSoft First Successful -> Spring Boot First Completed

MuleSoft XML:
```xml
<first-successful>
    <http:request config-ref="Primary_API" path="/v1/data" method="GET"/>
    <http:request config-ref="Secondary_API" path="/v1/data" method="GET"/>
    <http:request config-ref="Fallback_API" path="/v1/data" method="GET"/>
</first-successful>
```

Spring Boot Java:
```java
@Service
@Slf4j
public class ResilientDataService {

    private final List<DataApiClient> clients; // primary, secondary, fallback

    public DataDTO fetchData() {
        for (DataApiClient client : clients) {
            try {
                DataDTO result = client.getData();
                if (result != null) return result;
            } catch (Exception e) {
                log.warn("Client {} failed: {}", client.getName(), e.getMessage());
            }
        }
        throw new ServiceUnavailableException("All data sources failed");
    }

    // Or with CompletableFuture (race pattern):
    public DataDTO fetchDataRace() {
        CompletableFuture<DataDTO> primary = CompletableFuture.supplyAsync(() -> primaryClient.getData());
        CompletableFuture<DataDTO> secondary = CompletableFuture.supplyAsync(() -> secondaryClient.getData());
        return CompletableFuture.anyOf(primary, secondary)
            .thenApply(result -> (DataDTO) result)
            .orTimeout(5, TimeUnit.SECONDS)
            .join();
    }
}
```

Key mapping rules:
- MuleSoft first-successful maps to sequential try-catch fallback pattern.
- Try each source in order; return first successful result.
- For racing (fastest response), use CompletableFuture.anyOf().
- Log failures for each source for monitoring.""",
    },
    {
        "title": "Round Robin to Load Balancer",
        "category": "mulesoft",
        "content": """MuleSoft Round Robin -> Spring Boot Client-Side Load Balancing

MuleSoft XML:
```xml
<round-robin>
    <http:request config-ref="Server1_API" path="/v1/process" method="POST"/>
    <http:request config-ref="Server2_API" path="/v1/process" method="POST"/>
    <http:request config-ref="Server3_API" path="/v1/process" method="POST"/>
</round-robin>
```

Spring Boot Java:
```java
@Service
public class LoadBalancedService {
    private final List<String> servers = List.of(
        "https://server1.example.com",
        "https://server2.example.com",
        "https://server3.example.com");
    private final AtomicInteger counter = new AtomicInteger(0);
    private final WebClient.Builder webClientBuilder;

    public ProcessResult process(ProcessRequest request) {
        String server = servers.get(counter.getAndIncrement() % servers.size());
        return webClientBuilder.baseUrl(server).build()
            .post().uri("/v1/process")
            .bodyValue(request).retrieve()
            .bodyToMono(ProcessResult.class).block();
    }
}

// Or use Spring Cloud LoadBalancer:
@Configuration
public class LoadBalancerConfig {
    @Bean
    @LoadBalanced
    public WebClient.Builder loadBalancedWebClient() {
        return WebClient.builder();
    }
}
```

Key mapping rules:
- MuleSoft round-robin maps to client-side load balancing.
- Simple round-robin with AtomicInteger counter.
- For production, use Spring Cloud LoadBalancer with service discovery.
- @LoadBalanced WebClient resolves service names to instances.""",
    },
    {
        "title": "For Each to Stream.forEach",
        "category": "mulesoft",
        "content": """MuleSoft For Each -> Spring Boot Stream.forEach / for loop

MuleSoft XML:
```xml
<flow name="processItemsFlow">
    <foreach collection="#[payload.items]">
        <logger message="Processing item: #[payload.name]"/>
        <flow-ref name="processItem"/>
    </foreach>
</flow>
```

Spring Boot Java:
```java
@Service
@Slf4j
public class ItemProcessingService {
    public void processItems(List<Item> items) {
        items.forEach(item -> {
            log.info("Processing item: {}", item.getName());
            processItem(item);
        });
    }

    // Or with index tracking:
    public List<ItemResult> processItemsWithResults(List<Item> items) {
        return items.stream()
            .map(this::processItem)
            .collect(Collectors.toList());
    }
}
```

Key mapping rules:
- MuleSoft foreach maps to Java for loop, forEach(), or stream().
- payload inside foreach (current element) maps to lambda parameter.
- For results collection, use stream().map().collect().
- For side effects only, use forEach().""",
    },
    {
        "title": "Until Successful to @Retryable",
        "category": "mulesoft",
        "content": """MuleSoft Until Successful -> Spring Boot @Retryable

MuleSoft XML:
```xml
<flow name="retryableFlow">
    <until-successful maxRetries="5" millisBetweenRetries="3000">
        <http:request config-ref="External_API" path="/v1/submit" method="POST">
            <http:body>#[payload]</http:body>
        </http:request>
    </until-successful>
</flow>
```

Spring Boot Java:
```java
@Service
@Slf4j
public class SubmissionService {

    @Retryable(
        retryFor = {WebClientResponseException.class, WebClientRequestException.class},
        maxAttempts = 5,
        backoff = @Backoff(delay = 3000))
    public SubmitResult submit(SubmitRequest request) {
        log.info("Submitting request (attempt)");
        return webClient.post().uri("/v1/submit")
            .bodyValue(request).retrieve()
            .bodyToMono(SubmitResult.class).block();
    }

    @Recover
    public SubmitResult submitRecover(Exception ex, SubmitRequest request) {
        log.error("All submission attempts failed", ex);
        throw new ServiceUnavailableException("Submission failed after retries");
    }
}
```

Key mapping rules:
- MuleSoft until-successful maps to @Retryable annotation.
- maxRetries maps to maxAttempts.
- millisBetweenRetries maps to @Backoff(delay).
- @Recover method handles exhausted retries.
- Enable with @EnableRetry on a config class.""",
    },
    {
        "title": "Parallel For Each to parallelStream",
        "category": "mulesoft",
        "content": """MuleSoft Parallel For Each -> Spring Boot parallelStream / ExecutorService

MuleSoft XML:
```xml
<flow name="parallelProcessFlow">
    <parallel-foreach collection="#[payload.orders]" maxConcurrency="5">
        <http:request config-ref="External_API" path="/v1/validate/#[payload.id]" method="POST"/>
    </parallel-foreach>
</flow>
```

Spring Boot Java:
```java
@Service
public class ParallelValidationService {
    private final ExecutorService executor = Executors.newFixedThreadPool(5);

    public List<ValidationResult> validateAll(List<Order> orders) {
        List<CompletableFuture<ValidationResult>> futures = orders.stream()
            .map(order -> CompletableFuture.supplyAsync(() -> validate(order), executor))
            .toList();
        return futures.stream()
            .map(CompletableFuture::join)
            .collect(Collectors.toList());
    }

    // Simpler with parallelStream (less control):
    public List<ValidationResult> validateParallel(List<Order> orders) {
        return orders.parallelStream()
            .map(this::validate)
            .collect(Collectors.toList());
    }
}
```

Key mapping rules:
- MuleSoft parallel-foreach maps to CompletableFuture with ExecutorService.
- maxConcurrency maps to thread pool size.
- parallelStream is simpler but uses the common ForkJoinPool.
- For controlled concurrency, use ExecutorService with fixed thread pool.""",
    },
    {
        "title": "Try Scope to try-catch-finally",
        "category": "mulesoft",
        "content": """MuleSoft Try Scope -> Spring Boot try-catch-finally

MuleSoft XML:
```xml
<flow name="tryScopeFlow">
    <try>
        <http:request config-ref="External_API" path="/v1/process" method="POST"/>
        <logger message="Success: #[payload]"/>
        <error-handler>
            <on-error-continue type="HTTP:CONNECTIVITY">
                <logger level="WARN" message="API unreachable, using fallback"/>
                <set-payload value='{"status": "fallback"}'/>
            </on-error-continue>
            <on-error-propagate type="ANY">
                <logger level="ERROR" message="Unexpected error: #[error.description]"/>
            </on-error-propagate>
        </error-handler>
    </try>
</flow>
```

Spring Boot Java:
```java
@Service
@Slf4j
public class ProcessingService {
    public ProcessResult process(ProcessRequest request) {
        try {
            ProcessResult result = externalApiClient.process(request);
            log.info("Success: {}", result);
            return result;
        } catch (WebClientRequestException e) {
            log.warn("API unreachable, using fallback");
            return new ProcessResult("fallback");
        } catch (Exception e) {
            log.error("Unexpected error: {}", e.getMessage());
            throw e;
        }
    }
}
```

Key mapping rules:
- MuleSoft try scope maps to Java try-catch-finally.
- on-error-continue maps to catch that handles and continues.
- on-error-propagate maps to catch that re-throws.
- Specific error types map to specific exception classes in catch.""",
    },
    {
        "title": "Async Scope to @Async",
        "category": "mulesoft",
        "content": """MuleSoft Async Scope -> Spring Boot @Async

MuleSoft XML:
```xml
<flow name="mainFlow">
    <http:listener config-ref="HTTP_Listener" path="/api/orders" method="POST"/>
    <db:insert config-ref="Database_Config">
        <db:sql>INSERT INTO orders ...</db:sql>
    </db:insert>
    <async>
        <flow-ref name="sendNotification"/>
        <flow-ref name="updateAnalytics"/>
    </async>
    <set-payload value='{"status": "created"}'/>
</flow>
```

Spring Boot Java:
```java
@Service
public class OrderService {
    private final NotificationService notifications;
    private final AnalyticsService analytics;

    public OrderDTO createOrder(CreateOrderRequest request) {
        Order saved = repository.save(toEntity(request));
        // Fire and forget - async
        notifications.sendAsync(saved);
        analytics.trackAsync(saved);
        return toDTO(saved);
    }
}

@Service
@Slf4j
public class NotificationService {
    @Async
    public void sendAsync(Order order) {
        log.info("Sending notification for order {}", order.getId());
        emailService.send(order);
    }
}
```

Key mapping rules:
- MuleSoft async scope maps to @Async annotated methods.
- Code after async scope (set-payload) executes immediately.
- @Async runs in a separate thread pool.
- Main flow returns without waiting for async tasks.""",
    },
    {
        "title": "Sub-flow to Private Method or Service",
        "category": "mulesoft",
        "content": """MuleSoft Sub-flow -> Spring Boot Private Method / Service

MuleSoft XML:
```xml
<flow name="mainFlow">
    <http:listener config-ref="HTTP_Listener" path="/api/orders" method="POST"/>
    <flow-ref name="validateOrderSubflow"/>
    <flow-ref name="processPaymentSubflow"/>
    <flow-ref name="createOrderSubflow"/>
</flow>
<sub-flow name="validateOrderSubflow">
    <validation:is-not-null value="#[payload.customerId]"/>
    <validation:is-not-empty value="#[payload.items]"/>
</sub-flow>
<sub-flow name="processPaymentSubflow">
    <http:request config-ref="Payment_API" path="/v1/charge" method="POST"/>
</sub-flow>
```

Spring Boot Java:
```java
@Service
public class OrderService {
    private final PaymentService paymentService;

    public OrderDTO createOrder(CreateOrderRequest request) {
        validateOrder(request);
        PaymentResult payment = paymentService.charge(request.getPayment());
        Order order = buildOrder(request, payment);
        return toDTO(repository.save(order));
    }

    private void validateOrder(CreateOrderRequest request) {
        if (request.getCustomerId() == null) throw new BadRequestException("Customer ID required");
        if (request.getItems().isEmpty()) throw new BadRequestException("Items required");
    }

    private Order buildOrder(CreateOrderRequest request, PaymentResult payment) {
        Order order = new Order();
        order.setCustomerId(request.getCustomerId());
        order.setPaymentId(payment.getId());
        return order;
    }
}
```

Key mapping rules:
- MuleSoft sub-flow maps to private methods within the same service.
- Sub-flows used across flows map to separate @Service classes.
- flow-ref maps to method calls or service.method() calls.
- Keep sub-flow logic as private methods for encapsulation.""",
    },
    {
        "title": "Flow Reference to Service Injection",
        "category": "mulesoft",
        "content": """MuleSoft Flow Reference -> Spring Boot @Autowired Service Call

MuleSoft XML:
```xml
<flow name="orderFlow">
    <http:listener config-ref="HTTP_Listener" path="/api/orders" method="POST"/>
    <flow-ref name="inventoryFlow"/>
    <flow-ref name="shippingFlow"/>
</flow>
<flow name="inventoryFlow">
    <http:request config-ref="Inventory_API" path="/v1/reserve" method="POST"/>
</flow>
<flow name="shippingFlow">
    <http:request config-ref="Shipping_API" path="/v1/create" method="POST"/>
</flow>
```

Spring Boot Java:
```java
@Service
public class OrderOrchestrator {
    private final InventoryService inventoryService;
    private final ShippingService shippingService;

    public OrderResult processOrder(CreateOrderRequest request) {
        InventoryReservation reservation = inventoryService.reserve(request.getItems());
        ShipmentDTO shipment = shippingService.create(request.getShipping());
        return new OrderResult(reservation, shipment);
    }
}

@Service
public class InventoryService {
    private final WebClient inventoryClient;
    public InventoryReservation reserve(List<OrderItem> items) {
        return inventoryClient.post().uri("/v1/reserve").bodyValue(items)
            .retrieve().bodyToMono(InventoryReservation.class).block();
    }
}
```

Key mapping rules:
- MuleSoft flow-ref maps to injected service method calls.
- Each referenced flow becomes a separate @Service class.
- Dependency injection replaces config-ref references.
- The calling flow becomes an orchestrator service.""",
    },
    {
        "title": "Set Variable to Local Variable",
        "category": "mulesoft",
        "content": """MuleSoft Set Variable -> Spring Boot Local Variable

MuleSoft XML:
```xml
<flow name="variableFlow">
    <set-variable variableName="orderId" value="#[payload.id]"/>
    <set-variable variableName="timestamp" value="#[now()]"/>
    <set-variable variableName="fullName" value="#[payload.firstName ++ ' ' ++ payload.lastName]"/>
    <logger message="Processing order #[vars.orderId] for #[vars.fullName] at #[vars.timestamp]"/>
</flow>
```

Spring Boot Java:
```java
@Service
@Slf4j
public class OrderService {
    public void processOrder(OrderRequest request) {
        Long orderId = request.getId();
        LocalDateTime timestamp = LocalDateTime.now();
        String fullName = request.getFirstName() + " " + request.getLastName();
        log.info("Processing order {} for {} at {}", orderId, fullName, timestamp);
    }
}
```

Key mapping rules:
- MuleSoft set-variable maps to Java local variable declarations.
- vars.variableName maps to the local variable by name.
- DataWeave expressions map to Java expressions.
- Variables in Java have block scope; MuleSoft vars have flow scope.""",
    },
    {
        "title": "Set Payload to ResponseEntity.body",
        "category": "mulesoft",
        "content": """MuleSoft Set Payload -> Spring Boot ResponseEntity.body()

MuleSoft XML:
```xml
<flow name="responseFlow">
    <set-payload value='{"status": "success", "message": "Order created"}'/>
    <set-variable variableName="httpStatus" value="201"/>
</flow>
```

Spring Boot Java:
```java
@PostMapping("/orders")
public ResponseEntity<Map<String, String>> createOrder(@RequestBody OrderRequest request) {
    orderService.create(request);
    Map<String, String> response = Map.of("status", "success", "message", "Order created");
    return ResponseEntity.status(HttpStatus.CREATED).body(response);
}
```

Key mapping rules:
- MuleSoft set-payload maps to ResponseEntity.body() or return value.
- JSON string payload maps to a Map or DTO return type.
- httpStatus variable maps to ResponseEntity.status().
- Prefer typed DTOs over raw Maps for API responses.""",
    },
    {
        "title": "Logger to SLF4J Log Statements",
        "category": "mulesoft",
        "content": """MuleSoft Logger -> Spring Boot SLF4J

MuleSoft XML:
```xml
<logger level="INFO" message="Order #[payload.id] received from customer #[payload.customerId]"/>
<logger level="DEBUG" message="Full payload: #[payload]"/>
<logger level="WARN" message="Slow response from external API: #[attributes.responseTimeout]ms"/>
<logger level="ERROR" message="Failed to process order: #[error.description]"/>
```

Spring Boot Java:
```java
@Service
@Slf4j
public class OrderService {
    public void processOrder(Order order) {
        log.info("Order {} received from customer {}", order.getId(), order.getCustomerId());
        log.debug("Full payload: {}", order);
        // ...
        log.warn("Slow response from external API: {}ms", responseTime);
        // ...
        try { process(order); }
        catch (Exception e) { log.error("Failed to process order: {}", e.getMessage(), e); }
    }
}
```

Key mapping rules:
- MuleSoft logger level maps to log.info/debug/warn/error.
- MuleSoft #[expression] maps to {} placeholders in SLF4J.
- Always use parameterized logging with {} (not string concatenation).
- @Slf4j from Lombok auto-creates the logger field.
- Pass exception as last argument to log.error for stack trace.""",
    },
    {
        "title": "Transform Message to DTO Mapping",
        "category": "mulesoft",
        "content": """MuleSoft Transform Message -> Spring Boot DTO Mapping

MuleSoft XML:
```xml
<ee:transform>
    <ee:set-payload><![CDATA[%dw 2.0
output application/json
---
payload map {
    id: $.id,
    fullName: $.first_name ++ " " ++ $.last_name,
    email: $.email_address,
    active: $.status == "ACTIVE",
    tags: $.categories splitBy ","
}]]></ee:set-payload>
</ee:transform>
```

Spring Boot Java:
```java
@Component
public class CustomerMapper {
    public CustomerDTO toDTO(CustomerEntity entity) {
        CustomerDTO dto = new CustomerDTO();
        dto.setId(entity.getId());
        dto.setFullName(entity.getFirstName() + " " + entity.getLastName());
        dto.setEmail(entity.getEmailAddress());
        dto.setActive("ACTIVE".equals(entity.getStatus()));
        dto.setTags(entity.getCategories() != null
            ? Arrays.asList(entity.getCategories().split(",")) : List.of());
        return dto;
    }

    public List<CustomerDTO> toDTOList(List<CustomerEntity> entities) {
        return entities.stream().map(this::toDTO).collect(Collectors.toList());
    }
}
```

Key mapping rules:
- MuleSoft ee:transform maps to a Mapper class or MapStruct interface.
- DataWeave field mapping maps to getter/setter calls or constructor.
- String operations (++, splitBy) map to Java String methods.
- Boolean expressions map to Java boolean expressions.
- Create dedicated mapper classes for each entity-to-DTO conversion.""",
    },
    {
        "title": "Validation Module to Spring Validation",
        "category": "mulesoft",
        "content": """MuleSoft Validation Module -> Spring Boot @Valid + Custom Validators

MuleSoft XML:
```xml
<validation:all>
    <validation:is-not-null value="#[payload.email]" message="Email required"/>
    <validation:matches-regex value="#[payload.email]" regex="^[\\w.]+@[\\w.]+$"/>
    <validation:is-not-empty value="#[payload.items]" message="Items required"/>
    <validation:is-true expression="#[payload.totalAmount > 0]" message="Amount must be positive"/>
</validation:all>
```

Spring Boot Java:
```java
public class OrderRequest {
    @NotNull(message = "Email required")
    @Email
    private String email;

    @NotEmpty(message = "Items required")
    private List<ItemRequest> items;

    @Positive(message = "Amount must be positive")
    private BigDecimal totalAmount;
}

// Custom cross-field validator:
@Constraint(validatedBy = OrderValidator.class)
@Target(ElementType.TYPE)
@Retention(RetentionPolicy.RUNTIME)
public @interface ValidOrder {
    String message() default "Invalid order";
    Class<?>[] groups() default {};
    Class<? extends Payload>[] payload() default {};
}

public class OrderValidator implements ConstraintValidator<ValidOrder, OrderRequest> {
    @Override
    public boolean isValid(OrderRequest req, ConstraintValidatorContext ctx) {
        BigDecimal itemsTotal = req.getItems().stream()
            .map(i -> i.getPrice().multiply(BigDecimal.valueOf(i.getQuantity())))
            .reduce(BigDecimal.ZERO, BigDecimal::add);
        return itemsTotal.compareTo(req.getTotalAmount()) == 0;
    }
}
```

Key mapping rules:
- MuleSoft validation:all maps to @Valid with multiple annotations.
- is-not-null maps to @NotNull; is-not-empty maps to @NotEmpty.
- matches-regex maps to @Pattern or @Email.
- is-true with expression maps to custom @Constraint validator.
- Custom validators handle cross-field validation logic.""",
    },
    {
        "title": "Idempotent Message Validator to Redis Dedup",
        "category": "mulesoft",
        "content": """MuleSoft Idempotent Message Validator -> Spring Boot Redis Deduplication

MuleSoft XML:
```xml
<idempotent-message-validator idExpression="#[payload.messageId]"
    valueExpression="#[payload.messageId]"
    objectStore="idempotentStore">
    <os:object-store name="idempotentStore" persistent="true" entryTtl="86400" entryTtlUnit="SECONDS"/>
</idempotent-message-validator>
```

Spring Boot Java:
```java
@Service
public class IdempotentProcessor {
    private final StringRedisTemplate redis;
    private static final String PREFIX = "idempotent:";
    private static final Duration TTL = Duration.ofHours(24);

    public <T> T processIdempotent(String messageId, Supplier<T> processor) {
        String key = PREFIX + messageId;
        Boolean isNew = redis.opsForValue().setIfAbsent(key, "processing", TTL);
        if (Boolean.FALSE.equals(isNew)) {
            log.info("Duplicate message detected: {}", messageId);
            String cached = redis.opsForValue().get(key);
            if ("processing".equals(cached)) {
                throw new ConflictException("Message is being processed");
            }
            return objectMapper.readValue(cached, resultType);
        }
        try {
            T result = processor.get();
            redis.opsForValue().set(key, objectMapper.writeValueAsString(result), TTL);
            return result;
        } catch (Exception e) {
            redis.delete(key);
            throw e;
        }
    }
}

// Usage:
public OrderDTO createOrder(CreateOrderRequest request) {
    return idempotentProcessor.processIdempotent(
        request.getIdempotencyKey(),
        () -> doCreateOrder(request));
}
```

Key mapping rules:
- MuleSoft idempotent-message-validator maps to Redis setIfAbsent (SETNX).
- idExpression maps to the Redis key derived from message ID.
- objectStore with entryTtl maps to Redis key TTL.
- persistent=true maps to Redis (survives restarts).
- Use setIfAbsent for atomic check-and-set to prevent race conditions.""",
    },
    {
        "title": "Cache Scope to @Cacheable",
        "category": "mulesoft",
        "content": """MuleSoft Cache Scope -> Spring Boot @Cacheable

MuleSoft XML:
```xml
<ee:cache cachingStrategy-ref="configCache">
    <http:request config-ref="Config_API" path="/v1/settings" method="GET"/>
</ee:cache>
<ee:object-store-caching-strategy name="configCache" maxEntries="50" entryTtl="600" entryTtlUnit="SECONDS"/>
```

Spring Boot Java:
```java
@Service
public class ConfigService {

    @Cacheable(value = "settings", key = "'all'", unless = "#result == null")
    public SettingsDTO getSettings() {
        log.info("Cache MISS - fetching settings from API");
        return webClient.get().uri("/v1/settings")
            .retrieve().bodyToMono(SettingsDTO.class).block();
    }

    @Cacheable(value = "settings", key = "#key")
    public String getSetting(String key) {
        return webClient.get().uri("/v1/settings/{key}", key)
            .retrieve().bodyToMono(String.class).block();
    }

    @CacheEvict(value = "settings", allEntries = true)
    public void refreshSettings() {
        log.info("Settings cache evicted");
    }
}
```

Key mapping rules:
- MuleSoft ee:cache scope maps to @Cacheable annotation.
- cachingStrategy maxEntries and entryTtl map to cache manager config.
- Cache key maps to @Cacheable key attribute (SpEL expression).
- Use @CacheEvict for explicit cache invalidation.
- Configure TTL per cache in CacheManager bean.""",
    },
    # ==================================================================
    #  Additional documents to reach 200+
    # ==================================================================
    {
        "title": "SAP Connector to SAP JCo Integration",
        "category": "connector",
        "content": """MuleSoft SAP Connector -> Spring Boot SAP JCo / REST

MuleSoft XML:
```xml
<sap:config name="SAP_Config">
    <sap:simple-connection-provider-connection
        applicationServerHost="${sap.host}" systemNumber="${sap.systemNumber}"
        client="${sap.client}" userName="${sap.user}" password="${sap.password}"/>
</sap:config>
<flow name="callSapBapi">
    <sap:execute-synchronous-remote-function-call config-ref="SAP_Config"
        key="BAPI_CUSTOMER_GETLIST"/>
</flow>
```

Spring Boot Java:
```java
@Service
public class SapService {
    private final JCoDestination destination;

    public List<CustomerDTO> getCustomerList() throws JCoException {
        JCoFunction function = destination.getRepository().getFunction("BAPI_CUSTOMER_GETLIST");
        function.execute(destination);
        JCoTable customers = function.getTableParameterList().getTable("CUSTOMER_LIST");
        List<CustomerDTO> result = new ArrayList<>();
        for (int i = 0; i < customers.getNumRows(); i++) {
            customers.setRow(i);
            result.add(new CustomerDTO(
                customers.getString("CUSTOMER_NO"),
                customers.getString("CUSTOMER_NAME")));
        }
        return result;
    }
}
```

Key mapping rules:
- MuleSoft SAP connector maps to SAP JCo library calls.
- execute-synchronous-remote-function-call maps to JCoFunction.execute().
- SAP connection config maps to JCo destination properties.
- Table parameters map to JCoTable iteration.""",
    },
    {
        "title": "Performance Testing with JMeter Basics",
        "category": "testing",
        "content": """MuleSoft Performance Testing -> Spring Boot JMeter / Gatling

MuleSoft uses Anypoint Monitoring for performance metrics.

JMeter test plan (XML):
```xml
<TestPlan>
    <ThreadGroup>
        <num_threads>100</num_threads>
        <ramp_time>30</ramp_time>
        <HTTPSamplerProxy>
            <domain>localhost</domain>
            <port>8080</port>
            <path>/api/orders</path>
            <method>GET</method>
        </HTTPSamplerProxy>
    </ThreadGroup>
</TestPlan>
```

Spring Boot Java (Gatling alternative):
```java
// Gatling simulation in Scala/Java
public class OrderSimulation extends Simulation {
    HttpProtocolBuilder httpProtocol = http.baseUrl("http://localhost:8080");

    ScenarioBuilder scn = scenario("Order API Load Test")
        .exec(http("Get Orders").get("/api/orders").check(status().is(200)))
        .pause(1)
        .exec(http("Create Order").post("/api/orders")
            .body(StringBody("{\"customerId\": 1, \"items\": []}"))
            .check(status().is(201)));

    { setUp(scn.injectOpen(rampUsers(100).during(30))).protocols(httpProtocol); }
}
```

Key mapping rules:
- MuleSoft performance monitoring maps to JMeter or Gatling load tests.
- Thread groups define concurrent users and ramp-up time.
- Add performance tests for critical endpoints.
- Monitor with Actuator metrics during load tests.
- Target: p99 latency < 500ms, error rate < 0.1%.""",
    },
    {
        "title": "Memory Management Tips",
        "category": "performance",
        "content": """MuleSoft Memory Config -> Spring Boot Memory Management

MuleSoft wrapper.conf:
```properties
wrapper.java.maxmemory=4096
wrapper.java.additional=-XX:+UseG1GC
```

Spring Boot Java best practices:
```java
// 1. Stream large datasets instead of loading into memory
@Service
public class ExportService {
    @Transactional(readOnly = true)
    public void exportLargeDataset(OutputStream output) {
        try (Stream<Order> orders = orderRepository.streamAll()) {
            orders.forEach(order -> {
                writeCsvLine(output, order);
                entityManager.detach(order); // Free memory
            });
        }
    }
}

// 2. Use pagination for batch processing
public void processAllOrders() {
    int page = 0;
    Page<Order> batch;
    do {
        batch = orderRepository.findAll(PageRequest.of(page++, 100));
        batch.forEach(this::process);
        entityManager.clear(); // Release entities from persistence context
    } while (batch.hasNext());
}

// 3. Configure JVM memory
// -Xms1g -Xmx2g -XX:MaxMetaspaceSize=256m
// -XX:+UseG1GC -XX:MaxGCPauseMillis=200
```

application.yml:
```yaml
spring:
  jpa:
    open-in-view: false  # Prevent lazy loading in view layer (saves memory)
```

Key mapping rules:
- Stream large result sets with repository.streamAll() instead of findAll().
- Detach processed entities to free persistence context memory.
- Use pagination for batch processing.
- Set spring.jpa.open-in-view=false to prevent accidental lazy loading.
- Monitor heap usage via /actuator/metrics/jvm.memory.used.""",
    },
    {
        "title": "HATEOAS HAL Links",
        "category": "springboot",
        "content": """MuleSoft API Links -> Spring Boot HATEOAS HAL Format

MuleSoft XML:
```xml
<ee:transform>
    <ee:set-payload><![CDATA[%dw 2.0
output application/json
---
{
    id: payload.id,
    _links: {
        self: {href: "/api/orders/" ++ (payload.id as String)},
        collection: {href: "/api/orders"}
    }
}]]></ee:set-payload>
</ee:transform>
```

Spring Boot Java:
```java
@RestController
@RequestMapping("/api/orders")
public class OrderController {

    @GetMapping("/{id}")
    public EntityModel<OrderDTO> getOrder(@PathVariable Long id) {
        OrderDTO order = orderService.findById(id);
        return EntityModel.of(order,
            linkTo(methodOn(OrderController.class).getOrder(id)).withSelfRel(),
            linkTo(methodOn(OrderController.class).getAllOrders(Pageable.unpaged())).withRel("collection"));
    }
}
```

pom.xml:
```xml
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-hateoas</artifactId>
</dependency>
```

HAL JSON output:
```json
{
    "id": 1,
    "status": "ACTIVE",
    "_links": {
        "self": {"href": "http://localhost:8080/api/orders/1"},
        "collection": {"href": "http://localhost:8080/api/orders"}
    }
}
```

Key mapping rules:
- MuleSoft manual _links maps to Spring HATEOAS EntityModel.
- linkTo(methodOn()) generates type-safe hypermedia links.
- HAL is the default representation in Spring HATEOAS.
- Add spring-boot-starter-hateoas dependency for HAL support.""",
    },
    {
        "title": "WebSocket Implementation",
        "category": "api-patterns",
        "content": """MuleSoft WebSocket -> Spring Boot WebSocket with STOMP

MuleSoft XML:
```xml
<websocket:config name="WS_Config">
    <websocket:connection>
        <websocket:listener host="0.0.0.0" port="8081" path="/ws"/>
    </websocket:connection>
</websocket:config>
<flow name="wsMessageFlow">
    <websocket:on-inbound-message config-ref="WS_Config" path="/ws/chat"/>
    <logger message="WebSocket message received: #[payload]"/>
    <websocket:send config-ref="WS_Config" socketId="#[attributes.socketId]">
        <websocket:content>#[output application/json --- {echo: payload}]</websocket:content>
    </websocket:send>
</flow>
```

Spring Boot Java:
```java
@Configuration
@EnableWebSocketMessageBroker
public class WebSocketConfig implements WebSocketMessageBrokerConfigurer {
    @Override
    public void configureMessageBroker(MessageBrokerRegistry config) {
        config.enableSimpleBroker("/topic", "/queue");
        config.setApplicationDestinationPrefixes("/app");
    }
    @Override
    public void registerStompEndpoints(StompEndpointRegistry registry) {
        registry.addEndpoint("/ws").setAllowedOrigins("*").withSockJS();
    }
}

@Controller
@Slf4j
public class ChatController {
    @MessageMapping("/chat")
    @SendTo("/topic/messages")
    public ChatMessage handleMessage(ChatMessage message) {
        log.info("WebSocket message received: {}", message);
        return new ChatMessage(message.getFrom(), message.getText(), LocalDateTime.now());
    }

    // Direct messaging to a specific user:
    @Autowired private SimpMessagingTemplate messagingTemplate;

    public void sendToUser(String userId, Object payload) {
        messagingTemplate.convertAndSendToUser(userId, "/queue/notifications", payload);
    }
}
```

Key mapping rules:
- MuleSoft websocket:on-inbound-message maps to @MessageMapping.
- websocket:send to specific socket maps to SimpMessagingTemplate.convertAndSendToUser().
- Broadcast maps to @SendTo("/topic/...").
- Use STOMP protocol with SockJS for browser compatibility.
- Enable with @EnableWebSocketMessageBroker.""",
    },
]


# ═══════════════════════════════════════════════════════════════════════════
#  Seed function — callable from endpoint or CLI
# ═══════════════════════════════════════════════════════════════════════════

async def seed_all(clear_existing: bool = False) -> dict:
    """
    Index all knowledge documents into the RAG vector store.

    Args:
        clear_existing: If True, delete existing seeded docs before inserting.

    Returns:
        Summary dict with counts.
    """
    import rag_service
    from db import get_pool

    pool = await get_pool()

    # Optionally clear previous seed data
    if clear_existing:
        async with pool.acquire() as conn:
            deleted = await conn.execute(
                "DELETE FROM rag_documents WHERE metadata->>'source' = 'seed_knowledge'"
            )
            logger.info("seed.cleared_existing: %s", deleted)

    total = len(KNOWLEDGE_DOCUMENTS)
    indexed = 0
    errors = []

    for i, doc in enumerate(KNOWLEDGE_DOCUMENTS, 1):
        title = doc["title"]
        try:
            logger.info(
                "seed.indexing [%d/%d]: %s (%s)",
                i, total, title, doc["category"],
            )
            await rag_service.index_document(
                title=title,
                content=doc["content"],
                category=doc["category"],
                metadata={"source": "seed_knowledge", "version": "2.0"},
            )
            indexed += 1
            logger.info("seed.indexed [%d/%d]: %s", i, total, title)
        except Exception as exc:
            logger.error("seed.failed [%d/%d]: %s — %s", i, total, title, exc)
            errors.append({"title": title, "error": str(exc)})

    summary = {
        "total_submitted": total,
        "indexed": indexed,
        "errors": errors,
        "status": "completed" if not errors else "completed_with_errors",
    }
    logger.info("seed.complete: %s", summary)
    return summary


# ═══════════════════════════════════════════════════════════════════════════
#  CLI entrypoint
# ═══════════════════════════════════════════════════════════════════════════

def main():
    """Run the seed script from the command line."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Seed the RAG knowledge base with MuleSoft→Spring Boot patterns."
    )
    parser.add_argument(
        "--clear", action="store_true",
        help="Delete existing seed documents before inserting.",
    )
    args = parser.parse_args()

    result = asyncio.run(seed_all(clear_existing=args.clear))

    print("\n" + "=" * 60)
    print(f"  Seed complete: {result['indexed']}/{result['total_submitted']} documents indexed")
    if result["errors"]:
        print(f"  Errors: {len(result['errors'])}")
        for err in result["errors"]:
            print(f"    - {err['title']}: {err['error']}")
    print("=" * 60)

    sys.exit(0 if result["status"] == "completed" else 1)


if __name__ == "__main__":
    main()
