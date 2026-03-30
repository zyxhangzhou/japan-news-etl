package com.japannews.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;
import java.util.Map;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class QueryResponse {

    private String answer;
    private List<NewsArticle> articles;

    @JsonProperty("query_info")
    private Map<String, Object> queryInfo;
}
