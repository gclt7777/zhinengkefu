# Open WebUI Troubleshooting Guide

## Understanding the Open WebUI Architecture

The Open WebUI system is designed to streamline interactions between the client (your browser) and the Ollama API. At the heart of this design is a backend reverse proxy, enhancing security and resolving CORS issues.

- **How it Works**: The Open WebUI is designed to interact with the Ollama API through a specific route. When a request is made from the WebUI to Ollama, it is not directly sent to the Ollama API. Initially, the request is sent to the Open WebUI backend via `/ollama` route. From there, the backend is responsible for forwarding the request to the Ollama API. This forwarding is accomplished by using the route specified in the `OLLAMA_BASE_URL` environment variable. Therefore, a request made to `/ollama` in the WebUI is effectively the same as making a request to `OLLAMA_BASE_URL` in the backend. For instance, a request to `/ollama/api/tags` in the WebUI is equivalent to `OLLAMA_BASE_URL/api/tags` in the backend.

- **Security Benefits**: This design prevents direct exposure of the Ollama API to the frontend, safeguarding against potential CORS (Cross-Origin Resource Sharing) issues and unauthorized access. Requiring authentication to access the Ollama API further enhances this security layer.

## Open WebUI: Server Connection Error

If you're experiencing connection issues, it’s often due to the WebUI docker container not being able to reach the Ollama server at 127.0.0.1:11434 (host.docker.internal:11434) inside the container . Use the `--network=host` flag in your docker command to resolve this. Note that the port changes from 3000 to 8080, resulting in the link: `http://localhost:8080`.

**Example Docker Command**:

```bash
docker run -d --network=host -v open-webui:/app/backend/data -e OLLAMA_BASE_URL=http://127.0.0.1:11434 --name open-webui --restart always ghcr.io/open-webui/open-webui:main
```

### Error on Slow Responses for Ollama

Open WebUI has a default timeout of 5 minutes for Ollama to finish generating the response. If needed, this can be adjusted via the environment variable AIOHTTP_CLIENT_TIMEOUT, which sets the timeout in seconds.

### General Connection Errors

**Ensure Ollama Version is Up-to-Date**: Always start by checking that you have the latest version of Ollama. Visit [Ollama's official site](https://ollama.com/) for the latest updates.

**Troubleshooting Steps**:

1. **Verify Ollama URL Format**:
   - When running the Web UI container, ensure the `OLLAMA_BASE_URL` is correctly set. (e.g., `http://192.168.1.1:11434` for different host setups).
   - In the Open WebUI, navigate to "Settings" > "General".
   - Confirm that the Ollama Server URL is correctly set to `[OLLAMA URL]` (e.g., `http://localhost:11434`).

By following these enhanced troubleshooting steps, connection issues should be effectively resolved. For further assistance or queries, feel free to reach out to us on our community Discord.

## Login page does not show the **Sign up** button / 登录页没有“注册”入口

Open WebUI 会在创建首个账号后自动关闭公开注册入口，以防止未授权的访客自行开通账号。因此，即使前端与后端均已成功启动，登录页底部也可能只剩下“登录”按钮，而看不到“没有账号？注册”。

要重新开放注册，可以按以下顺序检查：

1. **通过管理后台开启注册**：使用现有管理员账号登录 WebUI，依次进入 **Settings → General → Authentication**，打开 **Enable New Sign Ups**（允许新用户注册）开关并保存。界面会调用 `/api/v1/auths/admin/config` 将配置 `ENABLE_SIGNUP` 持久化为 `true`，刷新登录页后即可看到注册按钮。
2. **无法登录管理员账号时的应急方案**：在重启 WebUI 前临时设置环境变量 `RESET_CONFIG_ON_START=true`，让应用在启动时执行 `reset_config()` 清空数据库中的配置覆盖值，再配合 `ENABLE_SIGNUP=true` 恢复默认的开放注册状态。完成管理员登录和必要设置后，请移除该临时变量，避免每次启动都重置配置。

> 提示：如果仍未看到注册表单，请确认 `FRONTEND_BUILD_DIR` 指向的前端构建目录存在（默认是 `backend/open_webui/build`）。构建缺失时 `open-webui serve` 会退回到“仅 API”模式，从而导致 `/auth` 等页面样式异常甚至返回 404。可在前端目录执行 `npm install && npm run build` 生成静态资源，再重新运行 `open-webui serve`。
