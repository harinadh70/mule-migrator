# Spring Data JPA Repository Patterns

## Overview

Spring Data JPA provides a repository abstraction over JPA that eliminates
boilerplate data-access code. When migrating MuleSoft Database connector
operations (`db:select`, `db:insert`, `db:update`, `db:delete`), JPA
repositories are the primary target pattern.

## Basic Repository

```java
@Entity
@Table(name = "users")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class User {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, length = 255)
    private String name;

    @Column(nullable = false, unique = true)
    private String email;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "department_id")
    private Department department;

    @Column(nullable = false)
    private boolean active = true;

    @CreationTimestamp
    @Column(updatable = false)
    private LocalDateTime createdAt;

    @UpdateTimestamp
    private LocalDateTime updatedAt;
}

public interface UserRepository extends JpaRepository<User, Long> {
}
```

## Derived Query Methods

Spring Data generates queries from method names automatically. This replaces
most simple `db:select` operations from MuleSoft.

```java
public interface UserRepository extends JpaRepository<User, Long> {

    // SELECT * FROM users WHERE email = ?
    Optional<User> findByEmail(String email);

    // SELECT * FROM users WHERE active = true
    List<User> findByActiveTrue();

    // SELECT * FROM users WHERE name LIKE '%keyword%'
    List<User> findByNameContainingIgnoreCase(String keyword);

    // SELECT * FROM users WHERE department_id = ? AND active = true
    List<User> findByDepartmentIdAndActiveTrue(Long departmentId);

    // SELECT * FROM users WHERE created_at > ? ORDER BY name ASC
    List<User> findByCreatedAtAfterOrderByNameAsc(LocalDateTime after);

    // SELECT * FROM users WHERE age BETWEEN ? AND ?
    List<User> findByAgeBetween(int min, int max);

    // SELECT * FROM users WHERE status IN (?, ?, ?)
    List<User> findByStatusIn(Collection<String> statuses);

    // SELECT COUNT(*) FROM users WHERE active = true
    long countByActiveTrue();

    // SELECT EXISTS(SELECT 1 FROM users WHERE email = ?)
    boolean existsByEmail(String email);

    // DELETE FROM users WHERE active = false
    @Transactional
    void deleteByActiveFalse();
}
```

## Custom JPQL Queries

For complex queries that cannot be expressed with derived method names:

```java
public interface UserRepository extends JpaRepository<User, Long> {

    @Query("SELECT u FROM User u JOIN FETCH u.department WHERE u.id = :id")
    Optional<User> findByIdWithDepartment(@Param("id") Long id);

    @Query("SELECT u FROM User u WHERE u.department.name = :deptName AND u.active = true")
    List<User> findActiveByDepartmentName(@Param("deptName") String departmentName);

    @Query("SELECT new com.example.dto.UserSummary(u.id, u.name, u.email, d.name) " +
           "FROM User u JOIN u.department d WHERE u.active = true")
    List<UserSummary> findAllActiveSummaries();

    @Query("SELECT u FROM User u WHERE " +
           "(:name IS NULL OR u.name LIKE %:name%) AND " +
           "(:email IS NULL OR u.email = :email) AND " +
           "(:active IS NULL OR u.active = :active)")
    Page<User> searchUsers(
        @Param("name") String name,
        @Param("email") String email,
        @Param("active") Boolean active,
        Pageable pageable);
}
```

## Native SQL Queries

For cases where JPQL is insufficient (e.g., database-specific functions):

```java
public interface UserRepository extends JpaRepository<User, Long> {

    @Query(value = "SELECT * FROM users WHERE MATCH(name, email) AGAINST(:term IN BOOLEAN MODE)",
           nativeQuery = true)
    List<User> fullTextSearch(@Param("term") String term);

    @Query(value = "SELECT u.department_id, d.name, COUNT(u.id) as user_count " +
                   "FROM users u JOIN departments d ON u.department_id = d.id " +
                   "GROUP BY u.department_id, d.name " +
                   "ORDER BY user_count DESC",
           nativeQuery = true)
    List<Object[]> departmentUserCounts();
}
```

## Modifying Queries

```java
public interface UserRepository extends JpaRepository<User, Long> {

    @Modifying
    @Transactional
    @Query("UPDATE User u SET u.active = false WHERE u.lastLoginAt < :cutoff")
    int deactivateInactiveUsers(@Param("cutoff") LocalDateTime cutoff);

    @Modifying
    @Transactional
    @Query("DELETE FROM User u WHERE u.active = false AND u.createdAt < :cutoff")
    int purgeInactiveUsers(@Param("cutoff") LocalDateTime cutoff);
}
```

## Pagination and Sorting

Replaces MuleSoft `LIMIT`/`OFFSET` patterns:

```java
// In the repository
Page<User> findByActiveTrue(Pageable pageable);

// In the controller
@GetMapping
public ResponseEntity<Page<UserDTO>> list(
        @RequestParam(defaultValue = "0") int page,
        @RequestParam(defaultValue = "20") int size,
        @RequestParam(defaultValue = "createdAt,desc") String sort) {

    String[] sortParts = sort.split(",");
    Sort.Direction direction = sortParts.length > 1
        ? Sort.Direction.fromString(sortParts[1])
        : Sort.Direction.ASC;
    Pageable pageable = PageRequest.of(page, size, Sort.by(direction, sortParts[0]));

    Page<UserDTO> users = userService.findAll(pageable);
    return ResponseEntity.ok(users);
}
```

## Specifications (Dynamic Queries)

For complex, dynamic filtering (replaces MuleSoft conditional query building):

```java
public class UserSpecifications {

    public static Specification<User> hasName(String name) {
        return (root, query, cb) ->
            name == null ? null : cb.like(cb.lower(root.get("name")), "%" + name.toLowerCase() + "%");
    }

    public static Specification<User> isActive(Boolean active) {
        return (root, query, cb) ->
            active == null ? null : cb.equal(root.get("active"), active);
    }

    public static Specification<User> inDepartment(Long departmentId) {
        return (root, query, cb) ->
            departmentId == null ? null : cb.equal(root.get("department").get("id"), departmentId);
    }

    public static Specification<User> createdAfter(LocalDateTime date) {
        return (root, query, cb) ->
            date == null ? null : cb.greaterThan(root.get("createdAt"), date);
    }
}

// Usage in service
public Page<User> search(UserSearchCriteria criteria, Pageable pageable) {
    Specification<User> spec = Specification
        .where(UserSpecifications.hasName(criteria.getName()))
        .and(UserSpecifications.isActive(criteria.getActive()))
        .and(UserSpecifications.inDepartment(criteria.getDepartmentId()))
        .and(UserSpecifications.createdAfter(criteria.getCreatedAfter()));
    return userRepository.findAll(spec, pageable);
}
```

## Auditing

```java
@EntityListeners(AuditingEntityListener.class)
@MappedSuperclass
public abstract class Auditable {

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

@Configuration
@EnableJpaAuditing
public class JpaConfig {
    @Bean
    public AuditorAware<String> auditorProvider() {
        return () -> Optional.ofNullable(SecurityContextHolder.getContext())
            .map(SecurityContext::getAuthentication)
            .map(Authentication::getName);
    }
}
```

## Projections (Replacing MuleSoft column-subset selects)

```java
// Interface-based projection
public interface UserNameProjection {
    String getName();
    String getEmail();
}

public interface UserRepository extends JpaRepository<User, Long> {
    List<UserNameProjection> findByActiveTrue();
}

// Class-based projection (DTO)
public record UserSummary(Long id, String name, String email) {}

@Query("SELECT new com.example.dto.UserSummary(u.id, u.name, u.email) FROM User u WHERE u.active = true")
List<UserSummary> findActiveSummaries();
```

## Transaction Management

```java
@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class OrderService {

    private final OrderRepository orderRepository;
    private final InventoryRepository inventoryRepository;

    @Transactional  // overrides class-level readOnly
    public Order placeOrder(CreateOrderRequest request) {
        // Deduct inventory
        inventoryRepository.decrementStock(request.getProductId(), request.getQuantity());

        // Create order
        Order order = Order.builder()
            .productId(request.getProductId())
            .quantity(request.getQuantity())
            .status(OrderStatus.PLACED)
            .build();

        return orderRepository.save(order);
    }
}
```
