package com.japannews.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.japannews.model.NewsArticle;
import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
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
public class LlmService {

    private static final URI OPENAI_URI = URI.create("https://api.openai.com/v1/chat/completions");

    private final ObjectMapper objectMapper;
    private final HttpClient httpClient = HttpClient.newHttpClient();

    @Value("${OPENAI_API_KEY:}")
    private String openAiApiKey;

    @Value("${OPENAI_ANSWER_MODEL:gpt-4.1-mini}")
    private String model;

    public String generateAnswer(String prompt, List<NewsArticle> articles, String originalQuery) {
        if (articles == null || articles.isEmpty()) {
            return "今天暂时没有找到相关新闻";
        }

        try {
            if (openAiApiKey == null || openAiApiKey.isBlank()) {
                log.warn("OPENAI_API_KEY is blank, using fallback answer for query={}", originalQuery);
                return fallbackAnswer(articles);
            }
            return callOpenAi(prompt);
        } catch (Exception e) {
            log.warn("Failed to generate answer with OpenAI, using fallback answer. query={}", originalQuery, e);
            return fallbackAnswer(articles);
        }
    }

    private String callOpenAi(String prompt) throws IOException, InterruptedException {
        Map<String, Object> requestBody = new HashMap<>();
        requestBody.put("model", model);
        requestBody.put("temperature", 0.2);
        requestBody.put(
            "messages",
            List.of(
                Map.of("role", "system", "content", "你是日本新闻问答助手，请用中文简洁回答。"),
                Map.of("role", "user", "content", prompt)
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
            throw new IOException("OpenAI answer content was empty");
        }
        return contentNode.asText();
    }

    private String fallbackAnswer(List<NewsArticle> articles) {
        StringBuilder builder = new StringBuilder();
        builder.append("以下是今天找到的相关新闻：\n");
        for (NewsArticle article : articles) {
            builder.append("- ")
                .append(article.getTitle())
                .append("（")
                .append(article.getSource())
                .append("）\n");
        }
        builder.append("参考来源：");
        builder.append(
            articles.stream()
                .map(NewsArticle::getSource)
                .distinct()
                .reduce((left, right) -> left + "、" + right)
                .orElse("无")
        );
        return builder.toString();
    }
}
