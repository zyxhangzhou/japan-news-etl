package com.japannews.model;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ParsedIntent {

    private LocalDate date;
    private String dateRange;
    private String category;
    @Builder.Default
    private List<String> keywords = new ArrayList<>();
}
