# Spring Boot Testing Patterns

## Overview

Spring Boot provides a rich testing framework built on JUnit 5 and Mockito.
When migrating from MuleSoft (which typically uses MUnit), the target testing
strategy uses `@WebMvcTest` for controller tests, `@DataJpaTest` for
repository tests, and `@SpringBootTest` for integration tests.

## Controller Tests with @WebMvcTest

`@WebMvcTest` loads only the web layer (controllers, filters, advice) and
auto-configures MockMvc. Service dependencies are replaced with `@MockBean`.

```java
@WebMvcTest(ProductController.class)
class ProductControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private ProductService productService;

    @Autowired
    private ObjectMapper objectMapper;

    @Test
    @DisplayName("GET /api/products/{id} - returns product when found")
    void getById_found() throws Exception {
        ProductDTO product = new ProductDTO(1L, "Widget", "A widget", BigDecimal.TEN, "Tools", LocalDateTime.now());
        when(productService.findById(1L)).thenReturn(Optional.of(product));

        mockMvc.perform(get("/api/products/{id}", 1L)
                .accept(MediaType.APPLICATION_JSON))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.name").value("Widget"))
            .andExpect(jsonPath("$.price").value(10));

        verify(productService).findById(1L);
    }

    @Test
    @DisplayName("GET /api/products/{id} - returns 404 when not found")
    void getById_notFound() throws Exception {
        when(productService.findById(999L)).thenReturn(Optional.empty());

        mockMvc.perform(get("/api/products/{id}", 999L))
            .andExpect(status().isNotFound());
    }

    @Test
    @DisplayName("POST /api/products - creates product with valid input")
    void create_valid() throws Exception {
        CreateProductRequest request = new CreateProductRequest("Widget", "desc", BigDecimal.TEN, 1L);
        ProductDTO created = new ProductDTO(1L, "Widget", "desc", BigDecimal.TEN, "Tools", LocalDateTime.now());
        when(productService.create(any(CreateProductRequest.class))).thenReturn(created);

        mockMvc.perform(post("/api/products")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(request)))
            .andExpect(status().isCreated())
            .andExpect(jsonPath("$.id").value(1))
            .andExpect(header().exists("Location"));
    }

    @Test
    @DisplayName("POST /api/products - returns 400 for invalid input")
    void create_invalid() throws Exception {
        String invalidJson = """
            { "name": "", "price": -5 }
            """;

        mockMvc.perform(post("/api/products")
                .contentType(MediaType.APPLICATION_JSON)
                .content(invalidJson))
            .andExpect(status().isBadRequest());
    }

    @Test
    @DisplayName("GET /api/products - returns paginated list")
    void list_paginated() throws Exception {
        List<ProductDTO> products = List.of(
            new ProductDTO(1L, "A", "desc", BigDecimal.ONE, "Cat", LocalDateTime.now()),
            new ProductDTO(2L, "B", "desc", BigDecimal.TEN, "Cat", LocalDateTime.now())
        );
        when(productService.findAll(any(Pageable.class)))
            .thenReturn(new PageImpl<>(products));

        mockMvc.perform(get("/api/products")
                .param("page", "0")
                .param("size", "20"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$", hasSize(2)));
    }
}
```

## Repository Tests with @DataJpaTest

`@DataJpaTest` auto-configures an embedded H2 database and scans for
`@Entity` and `Repository` beans. Use it to verify custom queries.

```java
@DataJpaTest
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
@Testcontainers
class UserRepositoryTest {

    @Container
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:15")
        .withDatabaseName("testdb");

    @DynamicPropertySource
    static void configureProperties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", postgres::getJdbcUrl);
        registry.add("spring.datasource.username", postgres::getUsername);
        registry.add("spring.datasource.password", postgres::getPassword);
    }

    @Autowired
    private UserRepository userRepository;

    @Autowired
    private TestEntityManager entityManager;

    @BeforeEach
    void setUp() {
        Department dept = entityManager.persistAndFlush(
            Department.builder().name("Engineering").build()
        );
        entityManager.persistAndFlush(
            User.builder().name("Alice").email("alice@example.com")
                .department(dept).active(true).build()
        );
        entityManager.persistAndFlush(
            User.builder().name("Bob").email("bob@example.com")
                .department(dept).active(false).build()
        );
    }

    @Test
    @DisplayName("findByActiveTrue returns only active users")
    void findByActiveTrue() {
        List<User> active = userRepository.findByActiveTrue();

        assertThat(active).hasSize(1);
        assertThat(active.get(0).getName()).isEqualTo("Alice");
    }

    @Test
    @DisplayName("findByEmail returns matching user")
    void findByEmail() {
        Optional<User> user = userRepository.findByEmail("alice@example.com");

        assertThat(user).isPresent();
        assertThat(user.get().getName()).isEqualTo("Alice");
    }

    @Test
    @DisplayName("findByEmail returns empty for unknown email")
    void findByEmail_notFound() {
        Optional<User> user = userRepository.findByEmail("unknown@example.com");

        assertThat(user).isEmpty();
    }
}
```

## Service Tests with Mockito

```java
@ExtendWith(MockitoExtension.class)
class OrderServiceTest {

    @Mock
    private OrderRepository orderRepository;

    @Mock
    private InventoryRepository inventoryRepository;

    @Mock
    private NotificationService notificationService;

    @InjectMocks
    private OrderService orderService;

    @Test
    @DisplayName("placeOrder creates order and deducts inventory")
    void placeOrder_success() {
        CreateOrderRequest request = new CreateOrderRequest("PROD-1", 5, "CUST-1");
        Order savedOrder = Order.builder()
            .id(1L).productId("PROD-1").quantity(5).status(OrderStatus.PLACED).build();

        when(inventoryRepository.getStock("PROD-1")).thenReturn(100);
        when(orderRepository.save(any(Order.class))).thenReturn(savedOrder);

        Order result = orderService.placeOrder(request);

        assertThat(result.getId()).isEqualTo(1L);
        assertThat(result.getStatus()).isEqualTo(OrderStatus.PLACED);
        verify(inventoryRepository).decrementStock("PROD-1", 5);
        verify(notificationService).sendOrderConfirmation(savedOrder);
    }

    @Test
    @DisplayName("placeOrder throws when insufficient stock")
    void placeOrder_insufficientStock() {
        CreateOrderRequest request = new CreateOrderRequest("PROD-1", 200, "CUST-1");
        when(inventoryRepository.getStock("PROD-1")).thenReturn(10);

        assertThatThrownBy(() -> orderService.placeOrder(request))
            .isInstanceOf(InsufficientStockException.class)
            .hasMessageContaining("PROD-1");

        verify(orderRepository, never()).save(any());
    }
}
```

## Integration Tests with @SpringBootTest

```java
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@Testcontainers
@ActiveProfiles("test")
class OrderIntegrationTest {

    @Container
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:15");

    @DynamicPropertySource
    static void configureProperties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", postgres::getJdbcUrl);
        registry.add("spring.datasource.username", postgres::getUsername);
        registry.add("spring.datasource.password", postgres::getPassword);
    }

    @Autowired
    private TestRestTemplate restTemplate;

    @Autowired
    private OrderRepository orderRepository;

    @Test
    @DisplayName("Full order lifecycle: create -> get -> update -> delete")
    void orderLifecycle() {
        // Create
        CreateOrderRequest createReq = new CreateOrderRequest("PROD-1", 3, "CUST-1");
        ResponseEntity<OrderDTO> createResp = restTemplate.postForEntity(
            "/api/orders", createReq, OrderDTO.class);

        assertThat(createResp.getStatusCode()).isEqualTo(HttpStatus.CREATED);
        Long orderId = createResp.getBody().id();

        // Read
        ResponseEntity<OrderDTO> getResp = restTemplate.getForEntity(
            "/api/orders/{id}", OrderDTO.class, orderId);
        assertThat(getResp.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(getResp.getBody().quantity()).isEqualTo(3);

        // Update
        UpdateOrderRequest updateReq = new UpdateOrderRequest(5);
        restTemplate.put("/api/orders/{id}", updateReq, orderId);

        // Verify update
        OrderDTO updated = restTemplate.getForObject("/api/orders/{id}", OrderDTO.class, orderId);
        assertThat(updated.quantity()).isEqualTo(5);

        // Delete
        restTemplate.delete("/api/orders/{id}", orderId);
        ResponseEntity<OrderDTO> deleted = restTemplate.getForEntity(
            "/api/orders/{id}", OrderDTO.class, orderId);
        assertThat(deleted.getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
    }
}
```

## Testing REST Clients (replacing MuleSoft HTTP Request tests)

```java
@RestClientTest(ExternalApiClient.class)
class ExternalApiClientTest {

    @Autowired
    private ExternalApiClient client;

    @Autowired
    private MockRestServiceServer server;

    @Autowired
    private ObjectMapper objectMapper;

    @Test
    @DisplayName("getUser returns user from external API")
    void getUser_success() throws Exception {
        UserResponse expected = new UserResponse("1", "Alice", "alice@example.com");

        server.expect(requestTo("/api/v1/users/1"))
            .andExpect(method(HttpMethod.GET))
            .andExpect(header("Authorization", "Bearer test-token"))
            .andRespond(withSuccess(
                objectMapper.writeValueAsString(expected),
                MediaType.APPLICATION_JSON));

        UserResponse result = client.getUser("1", "test-token");

        assertThat(result.name()).isEqualTo("Alice");
        server.verify();
    }

    @Test
    @DisplayName("getUser handles 404 gracefully")
    void getUser_notFound() {
        server.expect(requestTo("/api/v1/users/999"))
            .andRespond(withStatus(HttpStatus.NOT_FOUND));

        assertThatThrownBy(() -> client.getUser("999", "token"))
            .isInstanceOf(ResourceNotFoundException.class);
    }
}
```

## Testing Utilities

### Custom Assertions

```java
public class OrderAssert extends AbstractAssert<OrderAssert, Order> {

    public OrderAssert(Order actual) {
        super(actual, OrderAssert.class);
    }

    public static OrderAssert assertThat(Order actual) {
        return new OrderAssert(actual);
    }

    public OrderAssert hasStatus(OrderStatus expected) {
        isNotNull();
        if (actual.getStatus() != expected) {
            failWithMessage("Expected status <%s> but was <%s>", expected, actual.getStatus());
        }
        return this;
    }

    public OrderAssert belongsToCustomer(String customerId) {
        isNotNull();
        if (!actual.getCustomerId().equals(customerId)) {
            failWithMessage("Expected customer <%s> but was <%s>", customerId, actual.getCustomerId());
        }
        return this;
    }
}
```

### Test Data Builders

```java
public class TestDataFactory {

    public static User.UserBuilder aUser() {
        return User.builder()
            .name("Test User")
            .email("test@example.com")
            .active(true);
    }

    public static CreateOrderRequest.CreateOrderRequestBuilder anOrderRequest() {
        return CreateOrderRequest.builder()
            .productId("PROD-1")
            .quantity(1)
            .customerId("CUST-1");
    }
}
```

## Test Configuration

### application-test.yml

```yaml
spring:
  datasource:
    url: jdbc:h2:mem:testdb
    driver-class-name: org.h2.Driver
  jpa:
    hibernate:
      ddl-auto: create-drop
    database-platform: org.hibernate.dialect.H2Dialect
  main:
    allow-bean-definition-overriding: true

logging:
  level:
    org.springframework.test: DEBUG
    org.hibernate.SQL: DEBUG
```

### Common Test Base Class

```java
@SpringBootTest
@ActiveProfiles("test")
@Transactional
public abstract class BaseIntegrationTest {

    @Autowired
    protected TestEntityManager entityManager;

    protected void flushAndClear() {
        entityManager.flush();
        entityManager.clear();
    }
}
```
