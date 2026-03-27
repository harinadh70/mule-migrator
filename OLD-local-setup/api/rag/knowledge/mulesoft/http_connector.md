# MuleSoft HTTP Connector Reference

## HTTP Listener

The HTTP Listener is the primary inbound endpoint in MuleSoft 4. It exposes an
HTTP server that accepts requests and routes them to a flow.

### Listener Configuration

```xml
<http:listener-config name="HTTP_Listener_config"
                      doc:name="HTTP Listener config">
    <http:listener-connection host="0.0.0.0" port="8081"
                              protocol="HTTP" />
</http:listener-config>
```

### Basic Listener (GET endpoint)

```xml
<flow name="getOrdersFlow">
    <http:listener config-ref="HTTP_Listener_config"
                   path="/api/orders"
                   method="GET"
                   doc:name="GET /api/orders" />
    <logger level="INFO" message="Received GET /api/orders" />
    <!-- Business logic here -->
    <ee:transform>
        <ee:message>
            <ee:set-payload><![CDATA[%dw 2.0
output application/json
---
payload]]></ee:set-payload>
        </ee:message>
    </ee:transform>
</flow>
```

**Spring Boot equivalent:**

```java
@RestController
@RequestMapping("/api/orders")
public class OrderController {

    @GetMapping
    public ResponseEntity<List<Order>> getOrders() {
        log.info("Received GET /api/orders");
        List<Order> orders = orderService.findAll();
        return ResponseEntity.ok(orders);
    }
}
```

### POST Endpoint with JSON Body

```xml
<flow name="createOrderFlow">
    <http:listener config-ref="HTTP_Listener_config"
                   path="/api/orders"
                   method="POST"
                   doc:name="POST /api/orders" />
    <logger level="INFO"
            message='#["Creating order: " ++ payload.orderId]' />
    <ee:transform>
        <ee:message>
            <ee:set-payload><![CDATA[%dw 2.0
output application/json
---
{
    id: payload.orderId,
    status: "CREATED",
    createdAt: now()
}]]></ee:set-payload>
        </ee:message>
    </ee:transform>
</flow>
```

**Spring Boot equivalent:**

```java
@PostMapping
public ResponseEntity<Order> createOrder(@RequestBody @Valid OrderRequest request) {
    log.info("Creating order: {}", request.getOrderId());
    Order order = orderService.create(request);
    return ResponseEntity.status(HttpStatus.CREATED).body(order);
}
```

### Path Parameters

```xml
<flow name="getOrderByIdFlow">
    <http:listener config-ref="HTTP_Listener_config"
                   path="/api/orders/{orderId}"
                   method="GET" />
    <set-variable variableName="orderId"
                  value="#[attributes.uriParams.orderId]" />
    <logger level="INFO"
            message='#["Fetching order: " ++ vars.orderId]' />
</flow>
```

**Spring Boot equivalent:**

```java
@GetMapping("/{orderId}")
public ResponseEntity<Order> getOrderById(@PathVariable String orderId) {
    log.info("Fetching order: {}", orderId);
    return orderService.findById(orderId)
        .map(ResponseEntity::ok)
        .orElse(ResponseEntity.notFound().build());
}
```

### Query Parameters

```xml
<flow name="searchOrdersFlow">
    <http:listener config-ref="HTTP_Listener_config"
                   path="/api/orders"
                   method="GET" />
    <set-variable variableName="status"
                  value="#[attributes.queryParams.status]" />
    <set-variable variableName="page"
                  value="#[attributes.queryParams.page default 0]" />
</flow>
```

**Spring Boot equivalent:**

```java
@GetMapping
public ResponseEntity<Page<Order>> searchOrders(
        @RequestParam(required = false) String status,
        @RequestParam(defaultValue = "0") int page) {
    return ResponseEntity.ok(orderService.search(status, page));
}
```

## HTTP Request (Outbound)

The HTTP Request connector makes outbound HTTP calls to external services.

### Request Configuration

```xml
<http:request-config name="External_API_Config"
                     doc:name="HTTP Request configuration">
    <http:request-connection host="api.example.com"
                             port="443"
                             protocol="HTTPS" />
</http:request-config>
```

### Making a GET Request

```xml
<http:request config-ref="External_API_Config"
              method="GET"
              path="/api/v1/users/{userId}"
              doc:name="Get User">
    <http:uri-params>
        <http:uri-param key="userId" value="#[vars.userId]" />
    </http:uri-params>
    <http:headers>
        <http:header key="Authorization"
                     value='#["Bearer " ++ vars.accessToken]' />
    </http:headers>
</http:request>
```

**Spring Boot equivalent:**

```java
@Service
public class UserApiClient {

    private final RestTemplate restTemplate;

    public UserApiClient(RestTemplateBuilder builder) {
        this.restTemplate = builder
            .rootUri("https://api.example.com")
            .build();
    }

    public User getUser(String userId, String accessToken) {
        HttpHeaders headers = new HttpHeaders();
        headers.setBearerAuth(accessToken);
        HttpEntity<?> entity = new HttpEntity<>(headers);

        return restTemplate.exchange(
            "/api/v1/users/{userId}",
            HttpMethod.GET,
            entity,
            User.class,
            userId
        ).getBody();
    }
}
```

### Making a POST Request

```xml
<http:request config-ref="External_API_Config"
              method="POST"
              path="/api/v1/notifications"
              doc:name="Send Notification">
    <http:body><![CDATA[#[output application/json --- {
        "recipient": vars.email,
        "message": vars.message
    }]]]></http:body>
    <http:headers>
        <http:header key="Content-Type" value="application/json" />
    </http:headers>
</http:request>
```

**Spring Boot equivalent:**

```java
public void sendNotification(String email, String message) {
    NotificationRequest request = new NotificationRequest(email, message);
    restTemplate.postForEntity("/api/v1/notifications", request, Void.class);
}
```

## Error Handling

### HTTP Listener Error Response

```xml
<flow name="orderFlow">
    <http:listener config-ref="HTTP_Listener_config"
                   path="/api/orders" method="GET" />
    <!-- business logic -->
    <error-handler>
        <on-error-propagate type="HTTP:NOT_FOUND">
            <ee:transform>
                <ee:message>
                    <ee:set-payload><![CDATA[%dw 2.0
output application/json
---
{ error: "Resource not found" }]]></ee:set-payload>
                </ee:message>
            </ee:transform>
            <set-variable variableName="httpStatus" value="404" />
        </on-error-propagate>
        <on-error-propagate type="ANY">
            <ee:transform>
                <ee:message>
                    <ee:set-payload><![CDATA[%dw 2.0
output application/json
---
{ error: "Internal server error" }]]></ee:set-payload>
                </ee:message>
            </ee:transform>
            <set-variable variableName="httpStatus" value="500" />
        </on-error-propagate>
    </error-handler>
</flow>
```

**Spring Boot equivalent:**

```java
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(ResourceNotFoundException.class)
    public ResponseEntity<ErrorResponse> handleNotFound(ResourceNotFoundException ex) {
        return ResponseEntity.status(HttpStatus.NOT_FOUND)
            .body(new ErrorResponse("Resource not found"));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ErrorResponse> handleGeneral(Exception ex) {
        log.error("Unexpected error", ex);
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
            .body(new ErrorResponse("Internal server error"));
    }
}
```
