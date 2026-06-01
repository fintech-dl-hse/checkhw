package main

import (
	"context"
	"fmt"
	"strings"
	"time"

	"github.com/yandex-cloud/go-genproto/yandex/cloud/compute/v1"
	"github.com/yandex-cloud/go-genproto/yandex/cloud/operation"
	ycsdk "github.com/yandex-cloud/go-sdk"
)

// До этой даты gpu-agent runner (vllm для hw-agent) не тушится авто-стопом,
// чтобы модель оставалась поднятой и доступной по сети. После — тушится как обычно.
var t4gpuAgentKeepAliveUntil = time.Date(2026, 6, 20, 0, 0, 0, 0, time.UTC)

func stopComputeInstance(ctx context.Context, sdk *ycsdk.SDK, id string) (*operation.Operation, error) {
	// Операция запуска Compute Instance с указанным ID
	return sdk.Compute().Instance().Stop(ctx, &compute.StopInstanceRequest{InstanceId: id})
}

func StopComputeInstance(ctx context.Context) (*Response, error) {
	// Авторизация в SDK при помощи сервисного аккаунта
	sdk, err := ycsdk.Build(ctx, ycsdk.Config{
		// Вызов InstanceServiceAccount автоматически запрашивает IAM-токен и формирует
		// при помощи него данные для авторизации в SDK
		Credentials: ycsdk.InstanceServiceAccount(),
	})
	if err != nil {
		return nil, err
	}
	// Получение списка Compute Instance по заданному запросом FolderId
	listInstancesResponse, err := sdk.Compute().Instance().List(ctx, &compute.ListInstancesRequest{
		FolderId: FolderId,
	})
	if err != nil {
		return nil, err
	}
	instances := listInstancesResponse.GetInstances()
	count := 0
	// Фильтрация списка Compute Instance, фильтр: выключена, в тегах содержится тег, заданный запросом
	for _, i := range instances {
		if i.Name == "opencode-agent" {
			fmt.Println("Skip opencode-agent instance", i.Name)
			continue
		}
		// GPU agent runner (vllm для hw-agent) не тушим авто-стопом до дедлайна,
		// чтобы модель оставалась поднятой и доступной по сети. После — тушим как обычно.
		if strings.Contains(i.Name, "t4gpu-agent") && time.Now().Before(t4gpuAgentKeepAliveUntil) {
			fmt.Println("Skip t4gpu-agent instance until", t4gpuAgentKeepAliveUntil, i.Name)
			continue
		}
		if i.Status == compute.Instance_RUNNING {
			_, err := stopComputeInstance(ctx, sdk, i.GetId())
			if err != nil {
				return nil, err
			}
			count++
		}
	}
	return &Response{
		StatusCode: 200,
		Body:       fmt.Sprintf("Stopped %d instances", count),
	}, nil
}
