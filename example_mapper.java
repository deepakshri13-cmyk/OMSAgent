// Example MapStruct Mapper
package com.example.mapper;

import org.mapstruct.Mapper;
import org.mapstruct.Mapping;
import org.mapstruct.Mappings;

@Mapper(componentModel = "spring")
public interface UserMapper {
    
    @Mappings({
        @Mapping(source = "firstName", target = "name"),
        @Mapping(source = "emailAddress", target = "email"),
        @Mapping(source = "address.street", target = "streetAddress"),
        @Mapping(target = "id", ignore = true)
    })
    UserDTO toDTO(User user);
    
    @Mapping(source = "name", target = "firstName")
    User toEntity(UserDTO dto);
    
    // Implicit mapping (field names match)
    AccountDTO toAccountDTO(Account account);
}

// Example POJO Mapper
package com.example.mapper;

public class ProductMapper {
    
    public ProductDTO map(Product product) {
        ProductDTO dto = new ProductDTO();
        dto.setName(product.getName());
        dto.setPrice(product.getPrice());
        dto.setDescription(product.getDescription());
        return dto;
    }
    
    public Product convert(ProductDTO dto) {
        Product product = new Product();
        product.setName(dto.getName());
        product.setPrice(dto.getPrice());
        product.setDescription(dto.getDescription());
        return product;
    }
}

