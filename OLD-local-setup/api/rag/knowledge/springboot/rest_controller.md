# Spring Boot @RestController Patterns and Best Practices

## Overview

`@RestController` combines `@Controller` and `@ResponseBody`. It is the
primary mechanism for building RESTful APIs in Spring Boot and the standard
target when migrating MuleSoft HTTP Listener flows.

## Basic CRUD Controller

```java
@RestController
@RequestMapping("/api/v1/products")
@RequiredArgsConstructor
@Slf4j
public class ProductController {

    private final ProductService productService;

    @GetMapping
    public ResponseEntity<List<ProductDTO>> list(
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size) {
        Page<ProductDTO> products = productService.findAll(PageRequest.of(page, size));
        return ResponseEntity.ok(products.getContent());
    }

    @GetMapping("/{id}")
    public ResponseEntity<ProductDTO> getById(@PathVariable Long id) {
        return productService.findById(id)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }

    @PostMapping
    public ResponseEntity<ProductDTO> create(@RequestBody @Valid CreateProductRequest request) {
        ProductDTO created = productService.create(request);
        URI location = ServletUriComponentsBuilder.fromCurrentRequest()
            .path("/{id}")
            .buildAndExpand(created.getId())
            .toUri();
        return ResponseEntity.created(location).body(created);
    }

    @PutMapping("/{id}")
    public ResponseEntity<ProductDTO> update(
            @PathVariable Long id,
            @RequestBody @Valid UpdateProductRequest request) {
        return productService.update(id, request)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<Void> delete(@PathVariable Long id) {
        productService.delete(id);
        return ResponseEntity.noContent().build();
    }
}
```

## Request/Response DTOs with Validation

```java
public record CreateProductRequest(
    @NotBlank @Size(max = 255) String name,
    @NotBlank String description,
    @NotNull @Positive BigDecimal price,
    @NotNull Long categoryId
) {}

public record UpdateProductRequest(
    @Size(max = 255) String name,
    String description,
    @Positive BigDecimal price,
    Long categoryId
) {}

public record ProductDTO(
    Long id,
    String name,
    String description,
    BigDecimal price,
    String categoryName,
    LocalDateTime createdAt
) {}
```

## Content Negotiation

```java
@GetMapping(value = "/{id}", produces = {
    MediaType.APPLICATION_JSON_VALUE,
    MediaType.APPLICATION_XML_VALUE
})
public ResponseEntity<ProductDTO> getById(@PathVariable Long id) {
    return productService.findById(id)
        .map(ResponseEntity::ok)
        .orElse(ResponseEntity.notFound().build());
}
```

## File Upload

```java
@PostMapping(value = "/upload", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
public ResponseEntity<UploadResponse> upload(
        @RequestParam("file") MultipartFile file) {
    if (file.isEmpty()) {
        return ResponseEntity.badRequest().build();
    }
    String url = storageService.store(file);
    return ResponseEntity.ok(new UploadResponse(url, file.getOriginalFilename()));
}
```

## Request Headers and Cookies

```java
@GetMapping("/secure")
public ResponseEntity<DataDTO> secureEndpoint(
        @RequestHeader("Authorization") String authHeader,
        @RequestHeader(value = "X-Request-Id", required = false) String requestId,
        @CookieValue(value = "session", defaultValue = "") String sessionCookie) {
    log.info("Request ID: {}, Session: {}", requestId, sessionCookie);
    // ...
}
```

## Global Exception Handling

```java
@RestControllerAdvice
@Slf4j
public class GlobalExceptionHandler {

    @ExceptionHandler(ResourceNotFoundException.class)
    public ResponseEntity<ErrorResponse> handleNotFound(ResourceNotFoundException ex) {
        log.warn("Resource not found: {}", ex.getMessage());
        return ResponseEntity.status(HttpStatus.NOT_FOUND)
            .body(new ErrorResponse("NOT_FOUND", ex.getMessage()));
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ErrorResponse> handleValidation(MethodArgumentNotValidException ex) {
        List<String> errors = ex.getBindingResult().getFieldErrors().stream()
            .map(fe -> fe.getField() + ": " + fe.getDefaultMessage())
            .toList();
        return ResponseEntity.badRequest()
            .body(new ErrorResponse("VALIDATION_ERROR", String.join("; ", errors)));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ErrorResponse> handleGeneral(Exception ex) {
        log.error("Unexpected error", ex);
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
            .body(new ErrorResponse("INTERNAL_ERROR", "An unexpected error occurred"));
    }
}

public record ErrorResponse(String code, String message) {}
```

## HATEOAS Support

```java
@GetMapping("/{id}")
public EntityModel<ProductDTO> getById(@PathVariable Long id) {
    ProductDTO product = productService.findById(id)
        .orElseThrow(() -> new ResourceNotFoundException("Product", id));

    return EntityModel.of(product,
        linkTo(methodOn(ProductController.class).getById(id)).withSelfRel(),
        linkTo(methodOn(ProductController.class).list(0, 20)).withRel("products"));
}
```

## Async Endpoints

```java
@GetMapping("/report")
public CompletableFuture<ResponseEntity<ReportDTO>> generateReport(
        @RequestParam String type) {
    return productService.generateReportAsync(type)
        .thenApply(ResponseEntity::ok);
}
```

## Swagger/OpenAPI Documentation

```java
@RestController
@RequestMapping("/api/v1/products")
@Tag(name = "Products", description = "Product management operations")
public class ProductController {

    @Operation(
        summary = "Get product by ID",
        description = "Returns a single product identified by its ID"
    )
    @ApiResponses({
        @ApiResponse(responseCode = "200", description = "Product found"),
        @ApiResponse(responseCode = "404", description = "Product not found")
    })
    @GetMapping("/{id}")
    public ResponseEntity<ProductDTO> getById(
            @Parameter(description = "Product ID") @PathVariable Long id) {
        // ...
    }
}
```

## Versioning Strategies

### URI Versioning (recommended for MuleSoft migrations)

```java
@RestController
@RequestMapping("/api/v1/products")
public class ProductV1Controller { /* ... */ }

@RestController
@RequestMapping("/api/v2/products")
public class ProductV2Controller { /* ... */ }
```

### Header Versioning

```java
@GetMapping(value = "/products", headers = "X-API-VERSION=1")
public ResponseEntity<List<ProductV1DTO>> getProductsV1() { /* ... */ }

@GetMapping(value = "/products", headers = "X-API-VERSION=2")
public ResponseEntity<List<ProductV2DTO>> getProductsV2() { /* ... */ }
```

## Interceptors and Filters (replacing MuleSoft policies)

```java
@Component
public class RequestLoggingInterceptor implements HandlerInterceptor {

    @Override
    public boolean preHandle(HttpServletRequest request,
                             HttpServletResponse response,
                             Object handler) {
        log.info("{} {}", request.getMethod(), request.getRequestURI());
        request.setAttribute("startTime", System.currentTimeMillis());
        return true;
    }

    @Override
    public void afterCompletion(HttpServletRequest request,
                                HttpServletResponse response,
                                Object handler, Exception ex) {
        long start = (long) request.getAttribute("startTime");
        log.info("{} {} -> {} ({}ms)",
            request.getMethod(), request.getRequestURI(),
            response.getStatus(), System.currentTimeMillis() - start);
    }
}
```
