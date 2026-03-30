package com.japannews.repository;

import com.japannews.model.NewsArticle;
import java.util.List;
import java.util.UUID;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface NewsArticleRepository extends JpaRepository<NewsArticle, UUID> {

    @Query("""
        SELECT n
        FROM NewsArticle n
        WHERE LOWER(n.title) LIKE LOWER(CONCAT('%', :keyword, '%'))
           OR LOWER(COALESCE(n.summary, '')) LIKE LOWER(CONCAT('%', :keyword, '%'))
           OR LOWER(COALESCE(n.content, '')) LIKE LOWER(CONCAT('%', :keyword, '%'))
        ORDER BY n.publishedAt DESC
        """)
    List<NewsArticle> searchByKeyword(@Param("keyword") String keyword, Pageable pageable);

    List<NewsArticle> findByCategoryOrderByPublishedAtDesc(String category, Pageable pageable);
}
