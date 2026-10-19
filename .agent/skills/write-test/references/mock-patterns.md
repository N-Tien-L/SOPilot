# Mocking Patterns and Strategies

## General Guidelines
- **Mock at the boundaries:** Mock external APIs, databases, file systems, and message queues.
- **Don't mock data structures:** Use real data classes, lists, and dicts. Don't mock POJOs or Pydantic models.
- **Don't mock what you don't own:** Wrap external libraries in a facade if they are hard to mock.

## Java (Mockito)
- **when/thenReturn:** Stubbing return values.
  `when(repository.findById(1L)).thenReturn(Optional.of(user));`
- **verify:** Checking interactions.
  `verify(rabbitTemplate, times(1)).convertAndSend(eq("exchange"), eq("routingKey"), any());`
- **ArgumentCaptor:** Inspecting arguments passed to mocks.
  ```java
  ArgumentCaptor<User> captor = ArgumentCaptor.forClass(User.class);
  verify(repository).save(captor.capture());
  assertThat(captor.getValue().getName()).isEqualTo("Test");
  ```

## Python (unittest.mock & pytest monkeypatch)
- **patch:** Decorator/context manager to replace objects.
  ```python
  @patch("my_module.external_service.get_data")
  def test_something(mock_get_data):
      mock_get_data.return_value = {"status": "ok"}
  ```
- **AsyncMock:** For testing async functions in FastAPI.
  ```python
  mock_async_func = AsyncMock(return_value=True)
  ```
- **pytest monkeypatch:** Great for environment variables.
  `monkeypatch.setenv("API_KEY", "test_key")`

## TypeScript / NestJS (Jest Mocks)
- **jest.fn():** Basic function mocking.
  `const mockFn = jest.fn().mockResolvedValue('data');`
- **jest.spyOn():** Spy on existing objects.
  `jest.spyOn(service, 'method').mockReturnValue(true);`
- **Module mocking:**
  `jest.mock('axios');`
