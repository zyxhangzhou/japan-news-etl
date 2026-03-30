package com.japannews.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.japannews.model.NewsArticle;
import com.japannews.model.QueryRequest;
import com.japannews.model.QueryResponse;
import com.japannews.service.QueryService;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest(properties = {
    "spring.autoconfigure.exclude="
        + "org.springframework.boot.autoconfigure.jdbc.DataSourceAutoConfiguration,"
        + "org.springframework.boot.autoconfigure.orm.jpa.HibernateJpaAutoConfiguration,"
        + "org.springframework.boot.autoconfigure.data.redis.RedisAutoConfiguration"
})
@AutoConfigureMockMvc
class QueryControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @MockBean
    private QueryService queryService;

    @Test
    void postQueryReturnsStructuredResponse() throws Exception {
        QueryResponse response = QueryResponse.builder()
            .answer("这是今天的移民相关新闻摘要。")
            .articles(List.of(
                NewsArticle.builder()
                    .id(UUID.randomUUID())
                    .url("https://example.com/article-1")
                    .urlHash("hash-1")
                    .title("日本移民政策更新")
                    .summary("政策出现新变化")
                    .source("NHK World")
                    .category("immigration")
                    .language("zh")
                    .publishedAt(OffsetDateTime.parse("2026-03-31T07:00:00+09:00"))
                    .build()
            ))
            .queryInfo(Map.of(
                "original_query", "今天有什么移民新闻",
                "date", "2026-03-31",
                "category", "immigration",
                "keywords", List.of(),
                "article_count", 1
            ))
            .build();

        when(queryService.query(any(QueryRequest.class))).thenReturn(response);

        mockMvc.perform(post("/api/query")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(new QueryRequest("今天有什么移民新闻"))))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.answer").value("这是今天的移民相关新闻摘要。"))
            .andExpect(jsonPath("$.articles").isArray())
            .andExpect(jsonPath("$.articles[0].title").value("日本移民政策更新"))
            .andExpect(jsonPath("$.query_info").exists())
            .andExpect(jsonPath("$.query_info.original_query").value("今天有什么移民新闻"));
    }
}
