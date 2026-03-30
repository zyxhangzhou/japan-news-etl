package com.japannews.service;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.japannews.model.ParsedIntent;
import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.LocalDate;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

@Slf4j
@Service
@RequiredArgsConstructor
public class IntentParserService {

    private static final URI OPENAI_URI = URI.create("https://api.openai.com/v1/chat/completions");
    private static final ZoneId TOKYO_ZONE = ZoneId.of("Asia/Tokyo");
    private static final String SYSTEM_PROMPT = "你是查询意图解析器。从用户问题中提取查询参数，返回纯 JSON，不要其他内容。";
    private static final String USER_PROMPT_TEMPLATE = "解析以下查询的意图：\"%s\"\n返回格式：{\"date\": \"today|yesterday|null\", \"dateRange\": \"today|week|month|null\", \"category\": \"immigration|ai_tech|language_learning|null\", \"keywords\": []}";

    private final ObjectMapper objectMapper;
    private final HttpClient httpClient = HttpClient.newHttpClient();

    @Value("${OPENAI_API_KEY:}")
    private String openAiApiKey;

    @Value("${OPENAI_INTENT_MODEL:gpt-4.1-mini}")
    private String model;

    public ParsedIntent parse(String query) {
        String normalizedQuery = query == null ? "" : query.trim();

        try {
            if (openAiApiKey == null || openAiApiKey.isBlank()) {
                log.warn("OPENAI_API_KEY is blank, using default intent for query={}", normalizedQuery);
                ParsedIntent defaultIntent = defaultIntent();
                log.info("Intent parse result query={} result={}", normalizedQuery, defaultIntent);
                return defaultIntent;
            }

            String responseContent = callOpenAi(normalizedQuery);
            OpenAiIntentPayload payload = objectMapper.readValue(responseContent, OpenAiIntentPayload.class);
            ParsedIntent parsedIntent = toParsedIntent(payload);
            log.info("Intent parse result query={} result={}", normalizedQuery, parsedIntent);
            return parsedIntent;
        } catch (IOException | InterruptedException e) {
            Thread.currentThread().interrupt();
            log.warn("Intent parsing failed, using default intent. query={}", normalizedQuery, e);
            ParsedIntent defaultIntent = defaultIntent();
            log.info("Intent parse result query={} result={}", normalizedQuery, defaultIntent);
            return defaultIntent;
        } catch (Exception e) {
            log.warn("Intent parsing failed, using default intent. query={}", normalizedQuery, e);
            ParsedIntent defaultIntent = defaultIntent();
            log.info("Intent parse result query={} result={}", normalizedQuery, defaultIntent);
            return defaultIntent;
        }
    }

    private String callOpenAi(String query) throws IOException, InterruptedException {
        Map<String, Object> requestBody = new HashMap<>();
        requestBody.put("model", model);
        requestBody.put("temperature", 0);
        requestBody.put("response_format", Map.of("type", "json_object"));
        requestBody.put(
            "messages",
            List.of(
                Map.of("role", "system", "content", SYSTEM_PROMPT),
                Map.of("role", "user", "content", USER_PROMPT_TEMPLATE.formatted(query))
            )
        );

        HttpRequest request = HttpRequest.newBuilder(OPENAI_URI)
            .header("Authorization", "Bearer " + openAiApiKey)
            .header("Content-Type", "application/json")
            .POST(HttpRequest.BodyPublishers.ofString(objectMapper.writeValueAsString(requestBody)))
            .build();

        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
        if (response.statusCode() < 200 || response.statusCode() >= 300) {
            throw new IOException("OpenAI request failed with status " + response.statusCode() + ": " + response.body());
        }

        JsonNode root = objectMapper.readTree(response.body());
        JsonNode contentNode = root.path("choices").path(0).path("message").path("content");
        if (contentNode.isMissingNode() || contentNode.asText().isBlank()) {
            throw new IOException("OpenAI response content was empty");
        }
        return contentNode.asText();
    }

    private ParsedIntent toParsedIntent(OpenAiIntentPayload payload) {
        ParsedIntent intent = defaultIntent();
        if (payload == null) {
            return intent;
        }

        intent.setDate(resolveDate(payload.getDate()));
        intent.setDateRange(normalizeNullableEnum(payload.getDateRange(), List.of("today", "week", "month")));
        intent.setCategory(normalizeNullableEnum(payload.getCategory(), List.of("immigration", "ai_tech", "language_learning")));
        intent.setKeywords(payload.getKeywords() == null ? new ArrayList<>() : payload.getKeywords());
        return intent;
    }

    private LocalDate resolveDate(String rawDate) {
        if (rawDate == null || rawDate.isBlank() || "null".equalsIgnoreCase(rawDate)) {
            return null;
        }
        LocalDate today = LocalDate.now(TOKYO_ZONE);
        return switch (rawDate.toLowerCase()) {
            case "today" -> today;
            case "yesterday" -> today.minusDays(1);
            default -> null;
        };
    }

    private String normalizeNullableEnum(String value, List<String> allowedValues) {
        if (value == null || value.isBlank() || "null".equalsIgnoreCase(value)) {
            return null;
        }
        String normalized = value.trim().toLowerCase();
        return allowedValues.contains(normalized) ? normalized : null;
    }

    private ParsedIntent defaultIntent() {
        return ParsedIntent.builder()
            .date(LocalDate.now(TOKYO_ZONE))
            .dateRange(null)
            .category(null)
            .keywords(new ArrayList<>())
            .build();
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public static class OpenAiIntentPayload {

        private String date;
        private String dateRange;
        private String category;
        private List<String> keywords;

        public String getDate() {
            return date;
        }

        public void setDate(String date) {
            this.date = date;
        }

        public String getDateRange() {
            return dateRange;
        }

        public void setDateRange(String dateRange) {
            this.dateRange = dateRange;
        }

        public String getCategory() {
            return category;
        }

        public void setCategory(String category) {
            this.category = category;
        }

        public List<String> getKeywords() {
            return keywords;
        }

        public void setKeywords(List<String> keywords) {
            this.keywords = keywords;
        }
    }
}
