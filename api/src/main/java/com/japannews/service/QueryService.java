package com.japannews.service;

import com.japannews.model.NewsArticle;
import com.japannews.model.QueryRequest;
import com.japannews.model.QueryResponse;
import com.japannews.repository.NewsArticleRepository;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;

@Service
@RequiredArgsConstructor
public class QueryService {

    private static final int DEFAULT_PAGE_SIZE = 5;

    private final NewsArticleRepository newsArticleRepository;
    private final IntentParserService intentParserService;
    private final LlmService llmService;

    public QueryResponse query(QueryRequest request) {
        Map<String, Object> queryInfo = new HashMap<>(intentParserService.parse(request.getQuery()));
        List<NewsArticle> articles = findArticles(request.getQuery(), (String) queryInfo.get("detected_category"));

        queryInfo.put("article_count", articles.size());
        String answer = llmService.answer(request.getQuery(), articles, queryInfo);

        return QueryResponse.builder()
            .answer(answer)
            .articles(articles)
            .queryInfo(queryInfo)
            .build();
    }

    private List<NewsArticle> findArticles(String query, String category) {
        PageRequest pageable = PageRequest.of(0, DEFAULT_PAGE_SIZE);
        if (category != null && !category.isBlank()) {
            return newsArticleRepository.findByCategoryOrderByPublishedAtDesc(category, pageable);
        }
        return newsArticleRepository.searchByKeyword(query, pageable);
    }
}
