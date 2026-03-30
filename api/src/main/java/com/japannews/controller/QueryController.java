package com.japannews.controller;

import com.japannews.model.QueryRequest;
import com.japannews.model.QueryResponse;
import com.japannews.service.QueryService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/query")
@RequiredArgsConstructor
public class QueryController {

    private final QueryService queryService;

    @PostMapping
    public ResponseEntity<QueryResponse> query(@RequestBody QueryRequest request) {
        return ResponseEntity.ok(queryService.query(request));
    }
}
