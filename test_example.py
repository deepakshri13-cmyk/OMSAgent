#!/usr/bin/env python3
"""
Quick test script to verify the system works
"""
from main import CodeUnderstandingSME

# Test with example code
test_code = """
package com.example.mapper;

import org.mapstruct.Mapper;
import org.mapstruct.Mapping;

@Mapper
public interface UserMapper {
    @Mapping(source = "firstName", target = "name")
    @Mapping(source = "emailAddress", target = "email")
    UserDTO toDTO(User user);
}

public class ProductMapper {
    public ProductDTO map(Product product) {
        ProductDTO dto = new ProductDTO();
        dto.setName(product.getName());
        dto.setPrice(product.getPrice());
        return dto;
    }
}
"""

if __name__ == '__main__':
    print("Testing AI Code Understanding SME...")
    print("=" * 80)
    
    sme = CodeUnderstandingSME()
    results = sme.process_content(test_code, "test.java")
    sme.output_results(results)

