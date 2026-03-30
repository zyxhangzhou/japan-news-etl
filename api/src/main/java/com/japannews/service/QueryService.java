package com.japannews.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.japannews.model.NewsArticle;
import com.japannews.model.ParsedIntent;
import com.japannews.model.QueryRequest;
import com.japannews.model.QueryResponse;
import jakarta.persistence.EntityManager;
import jakarta.persistence.TypedQuery;
import jakarta.persistence.criteria.CriteriaBuilder;
import jakarta.persistence.criteria.CriteriaQuery;
import jakarta.persistence.criteria.Order;
import jakarta.persistence.criteria.Predicate;
import jakarta.persistence.criteria.Root;
import java.time.Duration;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.stream.Collectors;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

@Slf4j
@Service
@RequiredArgsConstructor
public class QueryService {

    private static final int MAX_RESULTS = 10;
    private static final Duration QUERY_CACHE_TTL = Duration.ofHours(1);
    private static final ZoneId TOKYO_ZONE = ZoneId.of("Asia/Tokyo");
    private static final TypeReference<List<NewsArticle>> NEWS_ARTICLE_LIST_TYPE = new TypeReference<>() {};

    private final IntentParserService intentParserService;
    private final LlmService llmService;
    private final EntityManager entityManager;
    private final StringRedisTemplate stringRedisTemplate;
    private final ObjectMapper objectMapper;

    public QueryResponse query(QueryRequest request) {
        ParsedIntent parsedIntent = intentParserService.parse(request.getQuery());
        List<NewsArticle> articles = executeQuery(parsedIntent);
        String answer = generateAnswer(articles, request.getQuery());

        Map<String, Object> queryInfo = new LinkedHashMap<>();
        queryInfo.put("original_query", request.getQuery());
        queryInfo.put("date", parsedIntent.getDate() == null ? null : parsedIntent.getDate().toString());
        queryInfo.put("dateRange", parsedIntent.getDateRange());
        queryInfo.put("category", parsedIntent.getCategory());
        queryInfo.put("keywords", parsedIntent.getKeywords());
        queryInfo.put("article_count", articles.size());

        return QueryResponse.builder()
            .answer(answer)
            .articles(articles)
            .queryInfo(queryInfo)
            .build();
    }

    public List<NewsArticle> executeQuery(ParsedIntent intent) {
        if (intent == null) {
            return List.of();
        }

        if (shouldUseCache(intent)) {
            String cacheKey = buildCacheKey(intent);
            List<NewsArticle> cachedArticles = getCachedArticles(cacheKey);
            if (cachedArticles != null) {
                log.info("Query cache hit key={}", cacheKey);
                return cachedArticles;
            }

            List<NewsArticle> queriedArticles = queryArticles(intent);
            cacheArticles(cacheKey, queriedArticles);
            return queriedArticles;
        }

        return queryArticles(intent);
    }

    public String generateAnswer(List<NewsArticle> articles, String originalQuery) {
        if (articles == null || articles.isEmpty()) {
            return "今天暂时没有找到相关新闻";
        }

        String articleBlock = articles.stream()
            .map(article -> String.format(
                Locale.ROOT,
                "标题：%s\n中文摘要：%s\n来源：%s\n发布时间：%s",
                defaultString(article.getTitle()),
                defaultString(article.getLlmSummaryZh()),
                defaultString(article.getSource()),
                article.getPublishedAt() == null ? "" : article.getPublishedAt().toString()
            ))
            .collect(Collectors.joining("\n\n"));

        String prompt = String.format(
            Locale.ROOT,
            "用户问题：%s\n以下是相关新闻（%d条）：\n%s\n请用中文简洁回答用户问题，并在最后列出参考来源。",
            defaultString(originalQuery),
            articles.size(),
            articleBlock
        );

        return llmService.generateAnswer(prompt, articles, originalQuery);
    }

    private List<NewsArticle> queryArticles(ParsedIntent intent) {
        CriteriaBuilder cb = entityManager.getCriteriaBuilder();
        CriteriaQuery<NewsArticle> cq = cb.createQuery(NewsArticle.class);
        Root<NewsArticle> root = cq.from(NewsArticle.class);

        List<Predicate> predicates = new ArrayList<>();

        LocalDate targetDate = intent.getDate();
        if (targetDate != null) {
            OffsetDateTime start = targetDate.atStartOfDay(TOKYO_ZONE).toOffsetDateTime();
            OffsetDateTime end = targetDate.plusDays(1).atStartOfDay(TOKYO_ZONE).toOffsetDateTime();
            predicates.add(cb.greaterThanOrEqualTo(root.get("publishedAt"), start));
            predicates.add(cb.lessThan(root.get("publishedAt"), end));
        }

        if (intent.getDateRange() != null) {
            LocalDate today = LocalDate.now(TOKYO_ZONE);
            LocalDate rangeStart = switch (intent.getDateRange()) {
                case "today" -> today;
                case "week" -> today.minusDays(6);
                case "month" -> today.minusDays(29);
                default -> null;
            };
            if (rangeStart != null) {
                OffsetDateTime start = rangeStart.atStartOfDay(TOKYO_ZONE).toOffsetDateTime();
                OffsetDateTime end = today.plusDays(1).atStartOfDay(TOKYO_ZONE).toOffsetDateTime();
                predicates.add(cb.greaterThanOrEqualTo(root.get("publishedAt"), start));
                predicates.add(cb.lessThan(root.get("publishedAt"), end));
            }
        }

        if (intent.getCategory() != null && !intent.getCategory().isBlank()) {
            predicates.add(cb.equal(root.get("category"), intent.getCategory()));
        }

        if (intent.getKeywords() != null && !intent.getKeywords().isEmpty()) {
            for (String keyword : intent.getKeywords()) {
                if (keyword == null || keyword.isBlank()) {
                    continue;
                }
                String likePattern = "%" + keyword.toLowerCase(Locale.ROOT) + "%";
                predicates.add(
                    cb.or(
                        cb.like(cb.lower(root.get("title")), likePattern),
                        cb.like(cb.lower(cb.coalesce(root.get("summary"), "")), likePattern)
                    )
                );
            }
        }

        cq.select(root)
            .where(predicates.toArray(Predicate[]::new));

        List<Order> orderBy = new ArrayList<>();
        orderBy.add(cb.desc(root.get("publishedAt")));
        cq.orderBy(orderBy);

        TypedQuery<NewsArticle> query = entityManager.createQuery(cq);
        query.setMaxResults(MAX_RESULTS);
        List<NewsArticle> articles = query.getResultList();
        log.info(
            "Executed article query date={} dateRange={} category={} keywords={} resultCount={}",
            intent.getDate(),
            intent.getDateRange(),
            intent.getCategory(),
            intent.getKeywords(),
            articles.size()
        );
        return articles;
    }

    private boolean shouldUseCache(ParsedIntent intent) {
        return intent.getKeywords() == null || intent.getKeywords().isEmpty();
    }

    private String buildCacheKey(ParsedIntent intent) {
        String datePart;
        if (intent.getDate() != null) {
            datePart = intent.getDate().toString();
        } else if (intent.getDateRange() != null) {
            datePart = intent.getDateRange();
        } else {
            datePart = "all";
        }

        String categoryPart = intent.getCategory() == null || intent.getCategory().isBlank()
            ? "all"
            : intent.getCategory();

        return "news:query:" + datePart + ":" + categoryPart;
    }

    private List<NewsArticle> getCachedArticles(String cacheKey) {
        try {
            String cachedJson = stringRedisTemplate.opsForValue().get(cacheKey);
            if (cachedJson == null || cachedJson.isBlank()) {
                return null;
            }
            return objectMapper.readValue(cachedJson, NEWS_ARTICLE_LIST_TYPE);
        } catch (Exception e) {
            log.warn("Failed to read query cache key={}", cacheKey, e);
            return null;
        }
    }

    private void cacheArticles(String cacheKey, List<NewsArticle> articles) {
        try {
            String payload = objectMapper.writeValueAsString(articles);
            stringRedisTemplate.opsForValue().set(cacheKey, payload, QUERY_CACHE_TTL);
        } catch (Exception e) {
            log.warn("Failed to write query cache key={}", cacheKey, e);
        }
    }

    private String defaultString(String value) {
        return Objects.requireNonNullElse(value, "");
    }
}
