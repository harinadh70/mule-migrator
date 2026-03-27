# MuleSoft Database Connector Reference

## Database Configuration

### MySQL Configuration

```xml
<db:config name="Database_Config" doc:name="Database Config">
    <db:my-sql-connection host="localhost"
                          port="3306"
                          user="root"
                          password="secret"
                          database="myapp" />
</db:config>
```

**Spring Boot equivalent (`application.yml`):**

```yaml
spring:
  datasource:
    url: jdbc:mysql://localhost:3306/myapp
    username: root
    password: secret
    driver-class-name: com.mysql.cj.jdbc.Driver
  jpa:
    hibernate:
      ddl-auto: validate
    show-sql: false
```

### PostgreSQL Configuration

```xml
<db:config name="Database_Config" doc:name="Database Config">
    <db:generic-connection
        url="jdbc:postgresql://localhost:5432/myapp"
        user="postgres"
        password="secret"
        driverClassName="org.postgresql.Driver" />
</db:config>
```

## SELECT Queries

### Simple Select All

```xml
<flow name="getAllUsersFlow">
    <http:listener config-ref="HTTP_Listener_config"
                   path="/api/users" method="GET" />
    <db:select config-ref="Database_Config" doc:name="Select all users">
        <db:sql>SELECT id, name, email FROM users WHERE active = true</db:sql>
    </db:select>
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
@Repository
public interface UserRepository extends JpaRepository<User, Long> {
    List<User> findByActiveTrue();
}

@RestController
@RequestMapping("/api/users")
public class UserController {

    private final UserRepository userRepository;

    @GetMapping
    public ResponseEntity<List<User>> getAllUsers() {
        return ResponseEntity.ok(userRepository.findByActiveTrue());
    }
}
```

### Parameterized Select

```xml
<flow name="getUserByIdFlow">
    <http:listener config-ref="HTTP_Listener_config"
                   path="/api/users/{userId}" method="GET" />
    <db:select config-ref="Database_Config"
               doc:name="Select user by ID">
        <db:sql>SELECT * FROM users WHERE id = :userId</db:sql>
        <db:input-parameters><![CDATA[#[{
            userId: attributes.uriParams.userId
        }]]]></db:input-parameters>
    </db:select>
    <ee:transform>
        <ee:message>
            <ee:set-payload><![CDATA[%dw 2.0
output application/json
---
payload[0]]]></ee:set-payload>
        </ee:message>
    </ee:transform>
</flow>
```

**Spring Boot equivalent:**

```java
@GetMapping("/{userId}")
public ResponseEntity<User> getUserById(@PathVariable Long userId) {
    return userRepository.findById(userId)
        .map(ResponseEntity::ok)
        .orElse(ResponseEntity.notFound().build());
}
```

### Select with Complex WHERE Clause

```xml
<db:select config-ref="Database_Config">
    <db:sql>
        SELECT u.*, d.name as department_name
        FROM users u
        JOIN departments d ON u.department_id = d.id
        WHERE u.status = :status
          AND u.created_at > :startDate
        ORDER BY u.name ASC
        LIMIT :limit OFFSET :offset
    </db:sql>
    <db:input-parameters><![CDATA[#[{
        status: vars.status,
        startDate: vars.startDate,
        limit: vars.pageSize,
        offset: vars.page * vars.pageSize
    }]]]></db:input-parameters>
</db:select>
```

**Spring Boot equivalent:**

```java
@Repository
public interface UserRepository extends JpaRepository<User, Long> {

    @Query("SELECT u FROM User u JOIN FETCH u.department d " +
           "WHERE u.status = :status AND u.createdAt > :startDate " +
           "ORDER BY u.name ASC")
    Page<User> findByStatusAndCreatedAfter(
        @Param("status") String status,
        @Param("startDate") LocalDateTime startDate,
        Pageable pageable);
}
```

## INSERT Operations

### Simple Insert

```xml
<flow name="createUserFlow">
    <http:listener config-ref="HTTP_Listener_config"
                   path="/api/users" method="POST" />
    <db:insert config-ref="Database_Config"
               doc:name="Insert user"
               autoGenerateKeys="true">
        <db:sql>
            INSERT INTO users (name, email, department_id, active)
            VALUES (:name, :email, :departmentId, true)
        </db:sql>
        <db:input-parameters><![CDATA[#[{
            name: payload.name,
            email: payload.email,
            departmentId: payload.departmentId
        }]]]></db:input-parameters>
    </db:insert>
    <ee:transform>
        <ee:message>
            <ee:set-payload><![CDATA[%dw 2.0
output application/json
---
{
    id: payload.generatedKeys.GENERATED_KEY,
    message: "User created successfully"
}]]></ee:set-payload>
        </ee:message>
    </ee:transform>
</flow>
```

**Spring Boot equivalent:**

```java
@PostMapping
public ResponseEntity<User> createUser(@RequestBody @Valid CreateUserRequest request) {
    User user = User.builder()
        .name(request.getName())
        .email(request.getEmail())
        .departmentId(request.getDepartmentId())
        .active(true)
        .build();
    User saved = userRepository.save(user);
    return ResponseEntity.status(HttpStatus.CREATED).body(saved);
}
```

## UPDATE Operations

```xml
<flow name="updateUserFlow">
    <http:listener config-ref="HTTP_Listener_config"
                   path="/api/users/{userId}" method="PUT" />
    <db:update config-ref="Database_Config" doc:name="Update user">
        <db:sql>
            UPDATE users SET name = :name, email = :email
            WHERE id = :userId
        </db:sql>
        <db:input-parameters><![CDATA[#[{
            userId: attributes.uriParams.userId,
            name: payload.name,
            email: payload.email
        }]]]></db:input-parameters>
    </db:update>
</flow>
```

**Spring Boot equivalent:**

```java
@PutMapping("/{userId}")
public ResponseEntity<User> updateUser(
        @PathVariable Long userId,
        @RequestBody @Valid UpdateUserRequest request) {
    return userRepository.findById(userId)
        .map(user -> {
            user.setName(request.getName());
            user.setEmail(request.getEmail());
            return ResponseEntity.ok(userRepository.save(user));
        })
        .orElse(ResponseEntity.notFound().build());
}
```

## DELETE Operations

```xml
<flow name="deleteUserFlow">
    <http:listener config-ref="HTTP_Listener_config"
                   path="/api/users/{userId}" method="DELETE" />
    <db:delete config-ref="Database_Config" doc:name="Delete user">
        <db:sql>DELETE FROM users WHERE id = :userId</db:sql>
        <db:input-parameters><![CDATA[#[{
            userId: attributes.uriParams.userId
        }]]]></db:input-parameters>
    </db:delete>
</flow>
```

**Spring Boot equivalent:**

```java
@DeleteMapping("/{userId}")
public ResponseEntity<Void> deleteUser(@PathVariable Long userId) {
    if (!userRepository.existsById(userId)) {
        return ResponseEntity.notFound().build();
    }
    userRepository.deleteById(userId);
    return ResponseEntity.noContent().build();
}
```

## Stored Procedures

```xml
<flow name="callProcedureFlow">
    <db:stored-procedure config-ref="Database_Config"
                         doc:name="Call stored procedure">
        <db:sql>CALL calculate_monthly_report(:month, :year)</db:sql>
        <db:input-parameters><![CDATA[#[{
            month: vars.month,
            year: vars.year
        }]]]></db:input-parameters>
    </db:stored-procedure>
</flow>
```

**Spring Boot equivalent:**

```java
@Repository
public class ReportRepository {

    @PersistenceContext
    private EntityManager em;

    public void calculateMonthlyReport(int month, int year) {
        StoredProcedureQuery query = em
            .createStoredProcedureQuery("calculate_monthly_report");
        query.registerStoredProcedureParameter("month", Integer.class, ParameterMode.IN);
        query.registerStoredProcedureParameter("year", Integer.class, ParameterMode.IN);
        query.setParameter("month", month);
        query.setParameter("year", year);
        query.execute();
    }
}
```

## Bulk / Batch Operations

### Bulk Insert in MuleSoft

```xml
<flow name="bulkInsertFlow">
    <foreach collection="#[payload]">
        <db:insert config-ref="Database_Config">
            <db:sql>
                INSERT INTO orders (product_id, quantity, customer_id)
                VALUES (:productId, :quantity, :customerId)
            </db:sql>
            <db:input-parameters><![CDATA[#[{
                productId: payload.productId,
                quantity: payload.quantity,
                customerId: payload.customerId
            }]]]></db:input-parameters>
        </db:insert>
    </foreach>
</flow>
```

**Spring Boot equivalent:**

```java
@Transactional
public List<Order> bulkInsert(List<CreateOrderRequest> requests) {
    List<Order> orders = requests.stream()
        .map(req -> Order.builder()
            .productId(req.getProductId())
            .quantity(req.getQuantity())
            .customerId(req.getCustomerId())
            .build())
        .collect(Collectors.toList());
    return orderRepository.saveAll(orders);
}
```
