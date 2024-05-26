package main

import (
	"context"
	"fmt"
	"strings"

	"github.com/yandex-cloud/go-genproto/yandex/cloud/compute/v1"
	"github.com/yandex-cloud/go-genproto/yandex/cloud/operation"
	ycsdk "github.com/yandex-cloud/go-sdk"
)

const FolderId = "b1gtgl0ktbrjt750ihta"

func startComputeInstance(ctx context.Context, sdk *ycsdk.SDK, id string) (*operation.Operation, error) {
	// Операция запуска Compute Instance с указанным ID
	return sdk.Compute().Instance().Start(ctx, &compute.StartInstanceRequest{InstanceId: id})
}

type Response struct {
	StatusCode int         `json:"statusCode"`
	Body       interface{} `json:"body"`
}

func StartComputeInstances(ctx context.Context) (*Response, error) {
	return StartComputeInstancesNameContains(ctx, "runner")
}

func StartComputeInstancesGPU(ctx context.Context) (*Response, error) {
	return StartComputeInstancesNameContains(ctx, "t4gpu")
}

func StartComputeInstancesNameContains(ctx context.Context, nameContains string) (*Response, error) {
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
		if !strings.Contains(i.Name, nameContains) {
			fmt.Println("Skip instanse name", i.Name, "name must contain", nameContains)
			continue
		}

		if i.Status != compute.Instance_RUNNING {
			_, err := startComputeInstance(ctx, sdk, i.GetId())
			if err != nil {
				return nil, err
			}
			count++
		}

	}
	return &Response{
		StatusCode: 200,
		Body:       fmt.Sprintf("Started %d instances", count),
	}, nil
}
