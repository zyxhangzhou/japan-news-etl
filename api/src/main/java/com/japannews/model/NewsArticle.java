package com.japannews.model;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.OffsetDateTime;
import java.util.UUID;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Entity
@Table(name = "news_articles")
public class NewsArticle {

    @Id
    private UUID id;

    @Column(nullable = false, unique = true)
    private String url;

    @Column(name = "url_hash", nullable = false, length = 32)
    private String urlHash;

    @Column(nullable = false)
    private String title;

    private String summary;

    @Column(columnDefinition = "TEXT")
    private String content;

    @Column(nullable = false, length = 100)
    private String source;

    @Column(nullable = false, length = 50)
    private String category;

    @Column(nullable = false, length = 10)
    private String language;

    @Column(name = "published_at")
    private OffsetDateTime publishedAt;

    @Column(name = "fetched_at", nullable = false)
    private OffsetDateTime fetchedAt;

    @Column(name = "llm_summary_ja")
    private String llmSummaryJa;

    @Column(name = "llm_summary_zh")
    private String llmSummaryZh;
}
