package main

import (
	"fmt"
	"net/http"
	"io"
	"math"
	"os"
	"strconv"
	"strings"

	"hash/crc32"
)

const CSV_FILES_PATH_PREFIX = "/function/storage/fintech-dl-hse-letters-answers"

type Response struct {
	StatusCode int         `json:"statusCode"`
	Body       interface{} `json:"body"`
}

func Handler(rw http.ResponseWriter, req *http.Request) {
	submitCSV := req.FormValue("submit")
	repoName := req.FormValue("repo_name")
	maxInvalidLettersCount, err := strconv.Atoi(req.FormValue("max_invalid_letters_count"))
	if err != nil {
		fmt.Printf("max_invalid_letters_count is invalid %s", req.FormValue("max_invalid_letters_count"))
		rw.WriteHeader(400)
		return
	}
	resultPoints, err := strconv.Atoi(req.FormValue("result_points"))
	if err != nil {
		rw.WriteHeader(400)
		fmt.Printf("result_points is invalid %s", req.FormValue("result_points"))
		return
	}

	ok := CheckLetters(repoName, submitCSV, maxInvalidLettersCount, resultPoints)
	if ok {
		rw.WriteHeader(200)
	} else {
		rw.WriteHeader(400)
	}

	variant := repoNameToVariant([]byte(repoName))

	fmt.Fprintf(rw, "ok=%#v\nvariant %d repo name hw-letters variant image url: https://storage.yandexcloud.net/fintech-dl-hse-letters/letters_%d.png\n", ok, variant, variant)

	return
}

const numVariants = 100

func repoNameToVariant(repoName []byte) uint32 {

	return crc32.ChecksumIEEE(repoName) % numVariants
}

func CheckLetters(repoName string, submitCSV string, maxInvalidLettersCount int, resultPoints int) bool {

	variant := repoNameToVariant([]byte(repoName))

	fmt.Println("variant ", variant, " repo name ", string(repoName), "variant image url:", fmt.Sprintf("https://storage.yandexcloud.net/fintech-dl-hse-letters/letters_%d.png", variant))

	lettersFileName := fmt.Sprintf("%s/letters_%d.csv", CSV_FILES_PATH_PREFIX, variant)
	lettersFileHandle, err := os.Open(lettersFileName)
	if err != nil {
		fmt.Printf("Can't open variant: %s\n", err.Error())
		return false
	}
	correctResult, err := io.ReadAll(lettersFileHandle)
	if err != nil {
		fmt.Println("Oops - something went wrong. Please, report this issue to your teacher")
		return false
	}

	var correctCounts = make(map[string]int)

	for lineNo, line := range strings.Split(string(correctResult), "\n") {

		line = strings.Trim(line, "\r\n")
		if line == "" {
			continue
		}

		letterCount := strings.SplitN(line, ",", 2)
		if len(letterCount) != 2 {
			fmt.Fprintf(os.Stderr, "Invalid line `%s` (row number: %d)\n", line, lineNo)
			return false
		}

		letter := strings.ToUpper(letterCount[0])
		count, err := strconv.Atoi(letterCount[1])
		if err != nil {
			fmt.Println("invalid integer in teacher's csv. Call d.tarasov")
			return false
		}

		correctCounts[letter] = count
	}

	sumInvalidLettersCount := 0
	invalidLetters := []string{}

	seenLetters := map[string]struct{}{}

	sumLetterCounts := 0

	for lineNo, line := range strings.Split(submitCSV, "\n") {

		line = strings.Trim(line, "\r\n")
		if line == "" {
			continue
		}

		letterCount := strings.SplitN(line, ",", 2)
		if len(letterCount) != 2 {
			fmt.Fprintf(os.Stderr, "Invalid line `%s` (row number: %d)\n", line, lineNo)
			return false
		}

		letter := strings.ToUpper(letterCount[0])
		count, err := strconv.Atoi(letterCount[1])

		sumLetterCounts += count

		if err != nil {
			fmt.Fprintf(os.Stderr, "Can't parse letter count: `%s` (row number: %d)\n", letterCount[1], lineNo)
			return false
		}

		if _, ok := seenLetters[letter]; ok {
			fmt.Fprintf(os.Stderr, "Letter duplicate `%s` (row number: %d)\n", line, lineNo)
			return false
		}

		seenLetters[letter] = struct{}{}

		if extpectedCount, ok := correctCounts[letter]; ok {
			delete(correctCounts, letter)
			if extpectedCount != count {
				invalidLetters = append(invalidLetters, letter)
				sumInvalidLettersCount += int(math.Abs(float64(extpectedCount - count)))
			}
		} else {
			fmt.Fprintf(os.Stderr, "Invalid letter `%s` (row number: %d)\n", letter, lineNo)
			return false
		}
	}

	fmt.Printf("unique invalid letters cnt=%d; sum invalid letters count=%d; step threshold=%d\n", len(invalidLetters), sumInvalidLettersCount, maxInvalidLettersCount)

	if len(correctCounts) > 0 {
		leftKeys := make([]string, 0, len(correctCounts))
		for k, _ := range correctCounts {
			leftKeys = append(leftKeys, k)
		}
		fmt.Printf("not all letters were passed in input file: %#v\n", leftKeys)
		return false
	}

	if sumInvalidLettersCount > maxInvalidLettersCount {
		return false
	}

	fmt.Printf("Step score: %d\n", resultPoints)
	return true
}
