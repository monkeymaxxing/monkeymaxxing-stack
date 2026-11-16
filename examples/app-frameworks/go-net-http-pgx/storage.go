package main

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/credentials"
	"github.com/aws/aws-sdk-go-v2/service/s3"
)

const maxUploadBytes = 5 * 1024 * 1024 // Bound memory per request for this small example.

type objectStorage struct {
	client *s3.Client
	bucket string
}

func openStorage() *objectStorage {
	client := s3.NewFromConfig(aws.Config{Region: "auto",
		Credentials:                credentials.NewStaticCredentialsProvider(required("R2_ACCESS_KEY_ID"), required("R2_SECRET_ACCESS_KEY"), ""),
		HTTPClient:                 &http.Client{Timeout: 10 * time.Second},
		RequestChecksumCalculation: aws.RequestChecksumCalculationWhenRequired,
		ResponseChecksumValidation: aws.ResponseChecksumValidationWhenRequired,
	}, func(o *s3.Options) { o.BaseEndpoint = aws.String(required("R2_ENDPOINT")); o.UsePathStyle = true })
	return &objectStorage{client, required("R2_BUCKET")}
}
func (s *objectStorage) put(ctx context.Context, key string, data []byte) error {
	_, err := s.client.PutObject(ctx, &s3.PutObjectInput{Bucket: &s.bucket, Key: &key, Body: bytes.NewReader(data), ContentType: aws.String("application/octet-stream")})
	return err
}
func (s *objectStorage) get(ctx context.Context, key string) ([]byte, error) {
	result, err := s.client.GetObject(ctx, &s3.GetObjectInput{Bucket: &s.bucket, Key: &key})
	if err != nil {
		return nil, err
	}
	defer result.Body.Close()
	data, err := io.ReadAll(io.LimitReader(result.Body, maxUploadBytes+1))
	if len(data) > maxUploadBytes {
		return nil, fmt.Errorf("stored object exceeds upload limit")
	}
	return data, err
}
func digest(data []byte) string { sum := sha256.Sum256(data); return hex.EncodeToString(sum[:]) }
