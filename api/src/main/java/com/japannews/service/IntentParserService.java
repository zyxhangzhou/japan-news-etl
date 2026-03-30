package com.japannews.service;

import java.util.HashMap;
import java.util.Locale;
import java.util.Map;
import org.springframework.stereotype.Service;

@Service
public class IntentParserService {

    public Map<String, Object> parse(String query) {
        String normalizedQuery = query == null ? "" : query.trim();
        String lowerQuery = normalizedQuery.toLowerCase(Locale.ROOT);
        String category = null;

        if (containsAny(lowerQuery, "immigration", "visa", "migrant", "foreigner", "移民", "签证", "外国人")) {
            category = "immigration";
        } else if (containsAny(lowerQuery, "ai", "tech", "startup", "半导体", "人工智能", "technology")) {
            category = "ai_tech";
        } else if (containsAny(lowerQuery, "language", "japanese", "日本語", "学習", "jlpt")) {
            category = "language_learning";
        }

        Map<String, Object> info = new HashMap<>();
        info.put("original_query", query);
        info.put("normalized_query", normalizedQuery);
        info.put("detected_category", category);
        return info;
    }

    private boolean containsAny(String query, String... keywords) {
        for (String keyword : keywords) {
            if (query.contains(keyword.toLowerCase(Locale.ROOT))) {
                return true;
            }
        }
        return false;
    }
}
