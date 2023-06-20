using BF1ServerTools.Helpers;

using RestSharp;

namespace BF1ServerTools.API;

public static class BF1API
{
    private const string _host = "https://sparta-gw.battlelog.com/jsonrpc/pc/api";

    private static readonly RestClient _client = null;

    /// <summary>
    /// 初始化
    /// </summary>
    static BF1API()
    {
        if (_client != null)
            return;

        // 不抛出相关错误
        var options = new RestClientOptions(_host)
        {
            MaxTimeout = 5000,
            ThrowOnAnyError = false,
            ThrowOnDeserializationError = false
        };

        // 判断是否使用代理
        if (Globals.IsUseProxy)
        {
            // 判断代理是否配置正确
            if (Globals.IPAddress != default && Globals.Port != default)
            {
                var proxy = new WebProxy()
                {
                    Address = new Uri($"http://{Globals.IPAddress}:{Globals.Port}"),
                };
                options.Proxy = proxy;
            }
        }

        _client = new RestClient(options);
    }

    /// <summary>
    /// 通用 POST 请求
    /// </summary>
    /// <typeparam name="T"></typeparam>
    /// <param name="reqBody"></param>
    /// <param name="sessionId"></param>
    /// <returns></returns>
    public static async Task<RespContent> PostAsync<T>(T reqBody, string sessionId = "") where T : class
    {
        var sw = new Stopwatch();
        sw.Start();
        var respContent = new RespContent();

        try
        {
            var request = new RestRequest()
                .AddJsonBody(reqBody);

            if (!string.IsNullOrWhiteSpace(sessionId))
                request.AddHeader("X-GatewaySession", sessionId);

            var response = await _client.ExecutePostAsync(request);
            respContent.HttpCode = response.StatusCode;

            if (response.StatusCode == HttpStatusCode.OK)
            {
                respContent.IsSuccess = true;
                respContent.Content = response.Content;
            }
            else
            {
                /*
                {
                    "jsonrpc": "2.0",
                    "id": "5a29116e-13bd-4e69-b80d-d6d815ba86ef",
                    "error": {
                        "message": "Invalid Params: no valid session",
                        "code": -32501
                    }
                }                
                 */

                var errorMessage = JsonHelper.JsonDeserialize<ErrorMessage>(response.Content);
                respContent.Content = $"({(int)respContent.HttpCode} {respContent.HttpCode}) {errorMessage.error.code} {errorMessage.error.message}";
            }
        }
        catch (Exception ex)
        {
            respContent.Content = ex.Message;
        }

        sw.Stop();
        respContent.ExecTime = sw.Elapsed.TotalSeconds;

        return respContent;
    }

    /// <summary>
    /// 根据AuthCode获取玩家SessionId
    /// </summary>
    /// <param name="authCode">通过本地重定向获取</param>
    /// <returns></returns>
    public static async Task<RespContent> GetEnvIdViaAuthCode(string authCode)
    {
        var reqBody = new
        {
            jsonrpc = "2.0",
            method = "Authentication.getEnvIdViaAuthCode",
            @params = new
            {
                authCode,
                locale = "zh-tw"
            },
            id = Guid.NewGuid()
        };

        return await PostAsync(reqBody);
    }

    /// <summary>
    /// 设置战地1 API语言为 繁体中文
    /// </summary>
    /// <param name="sessionId"></param>
    /// <returns></returns>
    public static async Task<RespContent> SetAPILocale(string sessionId)
    {
        var reqBody = new
        {
            jsonrpc = "2.0",
            method = "CompanionSettings.setLocale",
            @params = new
            {
                locale = "zh_TW"
            },
            id = Guid.NewGuid()
        };

        return await PostAsync(reqBody, sessionId);
    }

    /// <summary>
    /// 获取战地1欢迎语
    /// </summary>
    /// <param name="sessionId"></param>
    /// <returns></returns>
    public static async Task<RespContent> GetWelcomeMessage(string sessionId)
    {
        var reqBody = new
        {
            jsonrpc = "2.0",
            method = "Onboarding.welcomeMessage",
            @params = new
            {
                game = "tunguska",
                minutesToUTC = "-480"
            },
            id = Guid.NewGuid()
        };

        return await PostAsync(reqBody, sessionId);
    }

    /// <summary>
    /// 踢出目标玩家
    /// </summary>
    /// <param name="sessionId"></param>
    /// <param name="gameId"></param>
    /// <param name="personaId"></param>
    /// <param name="reason"></param>
    /// <returns></returns>
    public static async Task<RespContent> RSPKickPlayer(string sessionId, long gameId, long personaId, string reason)
    {
        var reqBody = new
        {
            jsonrpc = "2.0",
            method = "RSP.kickPlayer",
            @params = new
            {
                game = "tunguska",
                gameId,
                personaId,
                reason
            },
            id = Guid.NewGuid()
        };

        return await PostAsync(reqBody, sessionId);
    }

    /// <summary>
    /// 更换玩家到指定队伍
    /// </summary>
    /// <param name="sessionId"></param>
    /// <param name="gameId"></param>
    /// <param name="personaId"></param>
    /// <param name="teamId"></param>
    /// <returns></returns>
    public static async Task<RespContent> RSPMovePlayer(string sessionId, long gameId, long personaId, int teamId)
    {
        var reqBody = new
        {
            jsonrpc = "2.0",
            method = "RSP.movePlayer",
            @params = new
            {
                game = "tunguska",
                gameId,
                personaId,
                teamId,
                forceKill = true,
                moveParty = false
            },
            id = Guid.NewGuid()
        };

        return await PostAsync(reqBody, sessionId);
    }

    /// <summary>
    /// 更换服务器地图
    /// </summary>
    /// <param name="sessionId"></param>
    /// <param name="persistedGameId"></param>
    /// <param name="levelIndex"></param>
    /// <returns></returns>
    public static async Task<RespContent> RSPChooseLevel(string sessionId, string persistedGameId, int levelIndex)
    {
        var reqBody = new
        {
            jsonrpc = "2.0",
            method = "RSP.chooseLevel",
            @params = new
            {
                game = "tunguska",
                persistedGameId,
                levelIndex
            },
            id = Guid.NewGuid()
        };

        return await PostAsync(reqBody, sessionId);
    }

    /// <summary>
    /// 添加服务器管理员
    /// </summary>
    /// <param name="sessionId"></param>
    /// <param name="serverId"></param>
    /// <param name="personaName"></param>
    /// <returns></returns>
    public static async Task<RespContent> AddServerAdmin(string sessionId, int serverId, string personaName)
    {
        var reqBody = new
        {
            jsonrpc = "2.0",
            method = "RSP.addServerAdmin",
            @params = new
            {
                game = "tunguska",
                serverId,
                personaName
            },
            id = Guid.NewGuid()
        };

        return await PostAsync(reqBody, sessionId);
    }

    /// <summary>
    /// 移除服务器管理员
    /// </summary>
    /// <param name="sessionId"></param>
    /// <param name="serverId"></param>
    /// <param name="personaId"></param>
    /// <returns></returns>
    public static async Task<RespContent> RemoveServerAdmin(string sessionId, int serverId, long personaId)
    {
        var reqBody = new
        {
            jsonrpc = "2.0",
            method = "RSP.removeServerAdmin",
            @params = new
            {
                game = "tunguska",
                serverId,
                personaId
            },
            id = Guid.NewGuid()
        };

        return await PostAsync(reqBody, sessionId);
    }

    /// <summary>
    /// 添加服务器VIP
    /// </summary>
    /// <param name="sessionId"></param>
    /// <param name="serverId"></param>
    /// <param name="personaName"></param>
    /// <returns></returns>
    public static async Task<RespContent> AddServerVip(string sessionId, int serverId, string personaName)
    {
        var reqBody = new
        {
            jsonrpc = "2.0",
            method = "RSP.addServerVip",
            @params = new
            {
                game = "tunguska",
                serverId,
                personaName
            },
            id = Guid.NewGuid()
        };

        return await PostAsync(reqBody, sessionId);
    }

    /// <summary>
    /// 移除服务器VIP
    /// </summary>
    /// <param name="sessionId"></param>
    /// <param name="serverId"></param>
    /// <param name="personaId"></param>
    /// <returns></returns>
    public static async Task<RespContent> RemoveServerVip(string sessionId, int serverId, long personaId)
    {
        var reqBody = new
        {
            jsonrpc = "2.0",
            method = "RSP.removeServerVip",
            @params = new
            {
                game = "tunguska",
                serverId,
                personaId
            },
            id = Guid.NewGuid()
        };

        return await PostAsync(reqBody, sessionId);
    }

    /// <summary>
    /// 添加服务器BAN
    /// </summary>
    /// <param name="sessionId"></param>
    /// <param name="serverId"></param>
    /// <param name="personaName"></param>
    /// <returns></returns>
    public static async Task<RespContent> AddServerBan(string sessionId, int serverId, string personaName)
    {
        var reqBody = new
        {
            jsonrpc = "2.0",
            method = "RSP.addServerBan",
            @params = new
            {
                game = "tunguska",
                serverId,
                personaName
            },
            id = Guid.NewGuid()
        };

        return await PostAsync(reqBody, sessionId);
    }

    /// <summary>
    /// 移除服务器BAN
    /// </summary>
    /// <param name="sessionId"></param>
    /// <param name="serverId"></param>
    /// <param name="personaId"></param>
    /// <returns></returns>
    public static async Task<RespContent> RemoveServerBan(string sessionId, int serverId, long personaId)
    {
        var reqBody = new
        {
            jsonrpc = "2.0",
            method = "RSP.removeServerBan",
            @params = new
            {
                game = "tunguska",
                serverId,
                personaId
            },
            id = Guid.NewGuid()
        };

        return await PostAsync(reqBody, sessionId);
    }

    /// <summary>
    /// 获取服务器完整详情信息
    /// </summary>
    /// <param name="sessionId"></param>
    /// <param name="gameId"></param>
    /// <returns></returns>
    public static async Task<RespContent> GetFullServerDetails(string sessionId, long gameId)
    {
        var reqBody = new
        {
            jsonrpc = "2.0",
            method = "GameServer.getFullServerDetails",
            @params = new
            {
                game = "tunguska",
                gameId
            },
            id = Guid.NewGuid()
        };

        return await PostAsync(reqBody, sessionId);
    }

    /// <summary>
    /// 获取服务器RSP详情信息
    /// </summary>
    /// <param name="sessionId"></param>
    /// <param name="serverId"></param>
    /// <returns></returns>
    public static async Task<RespContent> GetServerDetails(string sessionId, int serverId)
    {
        var reqBody = new
        {
            jsonrpc = "2.0",
            method = "RSP.getServerDetails",
            @params = new
            {
                game = "tunguska",
                serverId
            },
            id = Guid.NewGuid()
        };

        return await PostAsync(reqBody, sessionId);
    }

    /// <summary>
    /// 更新服务器信息
    /// </summary>
    /// <param name="sessionId"></param>
    /// <param name="reqBody"></param>
    /// <returns></returns>
    public static async Task<RespContent> UpdateServer(string sessionId, UpdateServer reqBody)
    {
        return await PostAsync(reqBody, sessionId);
    }

    /// <summary>
    /// 搜索服务器
    /// </summary>
    /// <param name="sessionId"></param>
    /// <param name="serverName"></param>
    /// <returns></returns>
    public static async Task<RespContent> SearchServers(string sessionId, string serverName)
    {
        var reqBody = new
        {
            jsonrpc = "2.0",
            method = "GameServer.searchServers",
            @params = new
            {
                filterJson = "{\"version\":6,\"name\":\"" + serverName + "\"}",
                game = "tunguska",
                limit = 30,
                protocolVersion = "3779779"
            },
            id = Guid.NewGuid()
        };

        return await PostAsync(reqBody, sessionId);
    }

    /// <summary>
    /// 离开服务器
    /// </summary>
    /// <param name="sessionId"></param>
    /// <param name="gameId"></param>
    /// <returns></returns>
    public static async Task<RespContent> LeaveGame(string sessionId, long gameId)
    {
        var reqBody = new
        {
            jsonrpc = "2.0",
            method = "Game.leaveGame",
            @params = new
            {
                game = "tunguska",
                gameId
            },
            id = Guid.NewGuid()
        };

        return await PostAsync(reqBody, sessionId);
    }

    /// <summary>
    /// 通过玩家数字Id获取玩家相关信息
    /// </summary>
    /// <param name="sessionId"></param>
    /// <param name="personaId"></param>
    /// <returns></returns>
    public static async Task<RespContent> GetPersonasByIds(string sessionId, long personaId)
    {
        var reqBody = new
        {
            jsonrpc = "2.0",
            method = "RSP.getPersonasByIds",
            @params = new
            {
                game = "tunguska",
                personaIds = new[] { personaId }
            },
            id = Guid.NewGuid()
        };

        return await PostAsync(reqBody, sessionId);
    }

    /// <summary>
    /// 获取玩家基础数据
    /// </summary>
    /// <param name="sessionId"></param>
    /// <param name="personaId"></param>
    /// <returns></returns>
    public static async Task<RespContent> DetailedStatsByPersonaId(string sessionId, long personaId)
    {
        var reqBody = new
        {
            jsonrpc = "2.0",
            method = "Stats.detailedStatsByPersonaId",
            @params = new
            {
                game = "tunguska",
                personaId
            },
            id = Guid.NewGuid()
        };

        return await PostAsync(reqBody, sessionId);
    }

    /// <summary>
    /// 获取玩家武器数据
    /// </summary>
    /// <param name="sessionId"></param>
    /// <param name="personaId"></param>
    /// <returns></returns>
    public static async Task<RespContent> GetWeaponsByPersonaId(string sessionId, long personaId)
    {
        var reqBody = new
        {
            jsonrpc = "2.0",
            method = "Progression.getWeaponsByPersonaId",
            @params = new
            {
                game = "tunguska",
                personaId
            },
            id = Guid.NewGuid()
        };

        return await PostAsync(reqBody, sessionId);
    }

    /// <summary>
    /// 获取玩家载具数据
    /// </summary>
    /// <param name="sessionId"></param>
    /// <param name="personaId"></param>
    /// <returns></returns>
    public static async Task<RespContent> GetVehiclesByPersonaId(string sessionId, long personaId)
    {
        var reqBody = new
        {
            jsonrpc = "2.0",
            method = "Progression.getVehiclesByPersonaId",
            @params = new
            {
                game = "tunguska",
                personaId
            },
            id = Guid.NewGuid()
        };

        return await PostAsync(reqBody, sessionId);
    }

    /// <summary>
    /// 获取玩家正在游玩服务器
    /// </summary>
    /// <param name="sessionId"></param>
    /// <param name="personaId"></param>
    /// <returns></returns>
    public static async Task<RespContent> GetServersByPersonaIds(string sessionId, long personaId)
    {
        var reqBody = new
        {
            jsonrpc = "2.0",
            method = "GameServer.getServersByPersonaIds",
            @params = new
            {
                game = "tunguska",
                personaIds = new[] { personaId }
            },
            id = Guid.NewGuid()
        };

        return await PostAsync(reqBody, sessionId);
    }

    /// <summary>
    /// 获取玩家佩戴的图章
    /// </summary>
    /// <param name="sessionId"></param>
    /// <param name="personaId"></param>
    /// <returns></returns>
    public static async Task<RespContent> GetEquippedEmblem(string sessionId, long personaId)
    {
        var reqBody = new
        {
            jsonrpc = "2.0",
            method = "Emblems.getEquippedEmblem",
            @params = new
            {
                platform = "pc",
                personaId
            },
            id = Guid.NewGuid()
        };

        return await PostAsync(reqBody, sessionId);
    }
}
