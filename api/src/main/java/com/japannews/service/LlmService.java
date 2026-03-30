package com.japannews.service;

import com.japannews.model.NewsArticle;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;
import org.springframework.stereotype.Service;

@Service
public class LlmService {

    public String answer(String query, List<NewsArticle> articles, Map<String, Object> queryInfo) {
        if (articles == null || articles.isEmpty()) {
            return "No relevant articles were found for the current query.";
        }

        String titles = articles.stream()
            .limit(3)
            .map(NewsArticle::getTitle)
            .collect(Collectors.joining("; "));

        Object category = queryInfo.get("detected_category");
        if (category != null) {
            return "Found " + articles.size() + " related articles in category " + category + ". Top matches: " + titles;
        }
        return "Found " + articles.size() + " related articles for query '" + query + "'. Top matches: " + titles;
    }
}
