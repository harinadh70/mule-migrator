# DataWeave 2.0 Patterns and Java Equivalents

## Overview

DataWeave is MuleSoft's expression language for data transformation. During
migration to Spring Boot, DataWeave expressions must be converted to Java code
(typically using Jackson, MapStruct, or plain Java streams).

## Basic Transformations

### Map / Transform Arrays

**DataWeave:**

```dataweave
%dw 2.0
output application/json
---
payload map {
    fullName: $.firstName ++ " " ++ $.lastName,
    email: lower($.email),
    age: $.age as Number
}
```

**Java equivalent:**

```java
List<UserDTO> result = users.stream()
    .map(u -> UserDTO.builder()
        .fullName(u.getFirstName() + " " + u.getLastName())
        .email(u.getEmail().toLowerCase())
        .age(Integer.parseInt(u.getAge()))
        .build())
    .collect(Collectors.toList());
```

### Filter

**DataWeave:**

```dataweave
%dw 2.0
output application/json
---
payload filter $.status == "ACTIVE" and $.age > 18
```

**Java equivalent:**

```java
List<User> result = users.stream()
    .filter(u -> "ACTIVE".equals(u.getStatus()) && u.getAge() > 18)
    .collect(Collectors.toList());
```

### Reduce / Aggregate

**DataWeave:**

```dataweave
%dw 2.0
output application/json
---
{
    totalAmount: payload reduce ((item, acc = 0) -> acc + item.amount),
    count: sizeOf(payload)
}
```

**Java equivalent:**

```java
double totalAmount = orders.stream()
    .mapToDouble(Order::getAmount)
    .sum();
Map<String, Object> result = Map.of(
    "totalAmount", totalAmount,
    "count", orders.size()
);
```

### GroupBy

**DataWeave:**

```dataweave
%dw 2.0
output application/json
---
payload groupBy $.department
```

**Java equivalent:**

```java
Map<String, List<Employee>> grouped = employees.stream()
    .collect(Collectors.groupingBy(Employee::getDepartment));
```

### Flatten / FlatMap

**DataWeave:**

```dataweave
%dw 2.0
output application/json
---
payload.orders flatMap $.items
```

**Java equivalent:**

```java
List<Item> allItems = orders.stream()
    .flatMap(order -> order.getItems().stream())
    .collect(Collectors.toList());
```

## Object Manipulation

### Pluck (Object to Array)

**DataWeave:**

```dataweave
%dw 2.0
output application/json
---
payload pluck ((value, key) -> {
    fieldName: key as String,
    fieldValue: value
})
```

**Java equivalent:**

```java
// Using Jackson ObjectMapper
ObjectMapper mapper = new ObjectMapper();
Map<String, Object> map = mapper.convertValue(payload, new TypeReference<>() {});
List<FieldDTO> result = map.entrySet().stream()
    .map(e -> new FieldDTO(e.getKey(), e.getValue()))
    .collect(Collectors.toList());
```

### MapObject (Transform Object Keys/Values)

**DataWeave:**

```dataweave
%dw 2.0
output application/json
---
payload mapObject ((value, key) ->
    (lower(key as String)): upper(value as String)
)
```

**Java equivalent:**

```java
Map<String, String> result = original.entrySet().stream()
    .collect(Collectors.toMap(
        e -> e.getKey().toLowerCase(),
        e -> e.getValue().toUpperCase()
    ));
```

## String Operations

### String Manipulation

**DataWeave:**

```dataweave
%dw 2.0
output application/json
---
{
    upper: upper(payload.name),
    lower: lower(payload.name),
    trimmed: trim(payload.name),
    contains: payload.name contains "admin",
    replaced: payload.name replace "old" with "new",
    split: payload.csv splitBy ","
}
```

**Java equivalent:**

```java
Map<String, Object> result = Map.of(
    "upper", name.toUpperCase(),
    "lower", name.toLowerCase(),
    "trimmed", name.trim(),
    "contains", name.contains("admin"),
    "replaced", name.replace("old", "new"),
    "split", Arrays.asList(csv.split(","))
);
```

## Date/Time Operations

### Date Formatting

**DataWeave:**

```dataweave
%dw 2.0
output application/json
---
{
    formatted: payload.timestamp as String {format: "yyyy-MM-dd"},
    parsed: payload.dateStr as DateTime {format: "MM/dd/yyyy"},
    now: now() as String {format: "yyyy-MM-dd'T'HH:mm:ss"}
}
```

**Java equivalent:**

```java
DateTimeFormatter inputFormat = DateTimeFormatter.ofPattern("MM/dd/yyyy");
DateTimeFormatter outputFormat = DateTimeFormatter.ofPattern("yyyy-MM-dd");

Map<String, String> result = Map.of(
    "formatted", timestamp.format(outputFormat),
    "parsed", LocalDate.parse(dateStr, inputFormat).toString(),
    "now", LocalDateTime.now().format(DateTimeFormatter.ISO_LOCAL_DATE_TIME)
);
```

## Null Handling

### Default Values

**DataWeave:**

```dataweave
%dw 2.0
output application/json
---
{
    name: payload.name default "Unknown",
    age: payload.age default 0,
    tags: payload.tags default []
}
```

**Java equivalent:**

```java
String name = Optional.ofNullable(payload.getName()).orElse("Unknown");
int age = Optional.ofNullable(payload.getAge()).orElse(0);
List<String> tags = Optional.ofNullable(payload.getTags()).orElse(List.of());
```

### Null-Safe Navigation

**DataWeave:**

```dataweave
%dw 2.0
output application/json
---
payload.user.address.city default "N/A"
```

**Java equivalent:**

```java
String city = Optional.ofNullable(payload)
    .map(Payload::getUser)
    .map(User::getAddress)
    .map(Address::getCity)
    .orElse("N/A");
```

## Type Coercion

**DataWeave:**

```dataweave
%dw 2.0
output application/json
---
{
    asNumber: payload.value as Number,
    asString: payload.id as String,
    asBoolean: payload.flag as Boolean,
    asDate: payload.dateStr as Date {format: "yyyy-MM-dd"}
}
```

**Java equivalent:**

```java
double number = Double.parseDouble(payload.getValue());
String str = String.valueOf(payload.getId());
boolean flag = Boolean.parseBoolean(payload.getFlag());
LocalDate date = LocalDate.parse(payload.getDateStr(), DateTimeFormatter.ISO_DATE);
```

## XML to JSON Conversion

**DataWeave:**

```dataweave
%dw 2.0
input payload application/xml
output application/json
---
{
    orderId: payload.order.@id,
    items: payload.order.*item map {
        name: $.name,
        qty: $.quantity as Number
    }
}
```

**Java equivalent (using Jackson XML + JSON):**

```java
@JacksonXmlRootElement(localName = "order")
public class XmlOrder {
    @JacksonXmlProperty(isAttribute = true)
    private String id;

    @JacksonXmlElementWrapper(useWrapping = false)
    @JacksonXmlProperty(localName = "item")
    private List<XmlItem> items;
}

// Convert XML -> POJO -> JSON
XmlMapper xmlMapper = new XmlMapper();
XmlOrder xmlOrder = xmlMapper.readValue(xmlInput, XmlOrder.class);
ObjectMapper jsonMapper = new ObjectMapper();
String json = jsonMapper.writeValueAsString(xmlOrder);
```

## Conditional Logic

**DataWeave:**

```dataweave
%dw 2.0
output application/json
---
payload map {
    name: $.name,
    category: if ($.amount > 1000) "premium"
              else if ($.amount > 100) "standard"
              else "basic",
    discount: $.amount match {
        case amt if amt > 1000 -> 0.2
        case amt if amt > 100  -> 0.1
        else -> 0
    }
}
```

**Java equivalent:**

```java
List<OrderDTO> result = orders.stream()
    .map(o -> {
        String category;
        if (o.getAmount() > 1000) category = "premium";
        else if (o.getAmount() > 100) category = "standard";
        else category = "basic";

        double discount;
        if (o.getAmount() > 1000) discount = 0.2;
        else if (o.getAmount() > 100) discount = 0.1;
        else discount = 0.0;

        return new OrderDTO(o.getName(), category, discount);
    })
    .collect(Collectors.toList());
```
