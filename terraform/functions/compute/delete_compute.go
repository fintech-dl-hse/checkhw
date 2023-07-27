package main

import (
	"context"
	"fmt"

	"github.com/yandex-cloud/go-genproto/yandex/cloud/compute/v1"
	ycsdk "github.com/yandex-cloud/go-sdk"
)

func DeleteComputeInstance(ctx context.Context, request *Request) (*Response, error) {
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
		FolderId: request.FolderId,
	})
	if err != nil {
		return nil, err
	}
	instances := listInstancesResponse.GetInstances()
	count := 0
	// Фильтрация списка Compute Instance, фильтр: выключена, в тегах содержится тег, заданный запросом
	for _, i := range instances {
		labels := i.Labels
		if _, ok := labels[request.Tag]; ok && i.Status != compute.Instance_RUNNING {
			// Запуск удовлетворяющих фильтру Compute Instance
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
