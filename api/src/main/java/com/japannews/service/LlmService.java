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
import java.util.stream.Collectors;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

@Slf4j
@Service
@RequiredArgsConstructor
public class LlmService {

    private static final String SYSTEM_PROMPT = "You are a helpful multilingual Japan news assistant. Answer clearly in the user's language when possible.";

    private final ObjectMapper objectMapper;
    private final HttpClient httpClient = HttpClient.newHttpClient();

    @Value("${LLM_API_KEY:${OPENAI_API_KEY:}}")
    private String llmApiKey;

    @Value("${LLM_BASE_URL:${OPENAI_BASE_URL:https://api.moonshot.cn/v1}}")
    private String llmBaseUrl;

    @Value("${LLM_ANSWER_MODEL:${OPENAI_ANSWER_MODEL:kimi-k2-0905-preview}}")
    private String model;

    public String generateAnswer(String prompt, List<NewsArticle> articles, String originalQuery) {
        if (articles == null || articles.isEmpty()) {
            return "No relevant news was found.";
        }

        try {
            if (llmApiKey == null || llmApiKey.isBlank()) {
                log.warn("LLM_API_KEY/OPENAI_API_KEY is blank, using fallback answer for query={}", originalQuery);
                return fallbackAnswer(articles);
            }
            return callLlm(prompt);
        } catch (Exception e) {
            log.warn("Failed to generate answer with configured LLM, using fallback answer. query={}", originalQuery, e);
            return fallbackAnswer(articles);
        }
    }

    private String callLlm(String prompt) throws IOException, InterruptedException {
        Map<String, Object> requestBody = new HashMap<>();
        requestBody.put("model", model);
        requestBody.put("temperature", 0.2);
        requestBody.put(
            "messages",
            List.of(
                Map.of("role", "system", "content", SYSTEM_PROMPT),
                Map.of("role", "user", "content", prompt)
            )
        );

        HttpRequest request = HttpRequest.newBuilder(buildChatCompletionsUri())
            .header("Authorization", "Bearer " + llmApiKey)
            .header("Content-Type", "application/json")
            .POST(HttpRequest.BodyPublishers.ofString(objectMapper.writeValueAsString(requestBody)))
            .build();

        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
        if (response.statusCode() < 200 || response.statusCode() >= 300) {
            throw new IOException("LLM request failed with status " + response.statusCode() + ": " + response.body());
        }

        JsonNode root = objectMapper.readTree(response.body());
        JsonNode contentNode = root.path("choices").path(0).path("message").path("content");
        if (contentNode.isMissingNode() || contentNode.asText().isBlank()) {
            throw new IOException("LLM answer content was empty");
        }
        return contentNode.asText();
    }

    private URI buildChatCompletionsUri() {
        String normalizedBaseUrl = llmBaseUrl == null || llmBaseUrl.isBlank()
            ? "https://api.openai.com/v1"
            : llmBaseUrl.replaceAll("/+$", "");
        return URI.create(normalizedBaseUrl + "/chat/completions");
    }

    private String fallbackAnswer(List<NewsArticle> articles) {
        String titles = articles.stream()
            .limit(5)
            .map(article -> "- " + article.getTitle() + " (" + article.getSource() + ")")
            .collect(Collectors.joining("\n"));
        String sources = articles.stream()
            .map(NewsArticle::getSource)
            .distinct()
            .collect(Collectors.joining(", "));
        return "Here is a quick summary based on the retrieved articles:\n"
            + titles
            + "\nSources: "
            + (sources.isBlank() ? "unknown" : sources);
    }
}