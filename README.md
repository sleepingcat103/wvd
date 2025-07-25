# wvdas - 巫术daphne的自动挂机脚本
一个自带gui的巫术手游的刷怪脚本.

和其他流行的游戏自动脚本相比, 针对巫术手游具有的 ***复杂的网络环境*** 和 ***偶尔的性能波动*** 做了专门的特殊优化.

目前该仓库仍然处于建设中.

## 如何安装模拟器并设置脚本?
### 模拟器设置
- 下载蓝叠, 并在多开器里创建一个**安卓11**版本.
- 安装游戏apk.
- 初次加载遇到黑屏是正常现象, 等待一段时候后尝试重启游戏, 重复几次即可.
- 如果遇到google登录弹窗, 连续按返回即可.
- 模拟器已经**允许adb调试**. 位于"设置"-"高级"-"adb调试"的设置已经打开.
- 模拟器分辨率为**1600x900**, 240 dpi.

### ADB连接设置
- 脚本左上角的"adb路径"一般是C:\Program Files\BlueStacks_nxt\HD-Adb.exe. 如果你没有该路径, 可以从谷歌上下载一个adb.exe. (同样确保保存路径中没有中文.)
- 确保没有打开过任何其他模拟器, 确保任务管理器里没有其他adb.exe进程.

### 游戏整体设置
- 游戏为**英文版**.
- 画面设置为**中(速度优先)**.
- 调整画面为**30帧**, 地下城亮度为**最暗-25%亮度**.
- 在自动恢复界面, 勾选了"使用技能驱散异常状态".
- 在背包补充界面, 勾选了"将非补充对象的道具存入仓库Place all non-refill items in storage"和"与旅店住宿时自动补充 Automatically refill when staying at the inn.". (如果无法确认, 勾选"持有1个哈肯的钩爪Carry 1 Hook of Harken").
- 游戏地图**没有缩放**. 如已经进行了缩放, 推荐重新安装游戏. (未缩放过的游戏地图应为17个格子左右.)
- 计划使用的技能**必须放快捷栏**, 但是**不能放在左上角**的快捷栏.
- **关闭对话自动选择分支**. 目前皇女要钱和角鹫都是基于不自动选择分支做的.

### 关卡内部设置
- 游戏地图必须**探明所有区域**. 对于部分进行目标点判定的地图, 至少要探明目标区域的全部地图.
- 游戏内最好已经解锁了目标地图所属的大哈肯.
- 勾选"一场战斗仅释放一次全体aoe"后, 只会释放一次被启用的LA系魔法和秘术. 但仍然需要手动启用秘术或全体aoe.
- 勾选"全体aoe后自动战斗", 会在释放了aoe后变为自动战斗. 但仍然需要手动启用秘术或全体aoe.
- 如果遇到sp不足, 会自动切换成lv1的技能释放. 但是之后的战斗会一直使用lv1技能. 如果想避免这种情况, 请调整住宿间隔.
- 如果出现人物卡在副本里导致的地图无法识别, 请将主角面具放置在**左上**位置, 以避免恢复导致的人物卡在副本里.
- 如果出现人物一进副本就卡住无法移动, 这是由于网络问题引起的, 请更换加速器.

### 脚本设置
- "智能开箱"是基于图像识别和拟合三角波来做预测的.
	- 目前是通过20张截图来预测的, 比较耗费时间.*(将会在未来版本中修复!)*
- "开箱人选: 随机"会随机指定人物. 如果指定了固定角色, 那么在尝试点击并失败5次后临时变为随机人选.
- 旅店休息间隔是间隔多少次地下城休息. 0代表一直休息, 1代表间隔一次休息, 以此类推. 关闭"启用旅店休息"后, 在刷图地下城和部分任务地下城将永久跳过旅店休息.
- "战斗后恢复"和"开启宝箱后恢复"是指在这两个动作后执行的自动恢复操作. 如果恢复没有驱散异常, 检查游戏设置, 角色技能以及角色异常状态.
#### 三牛任务:
- 从时空跳跃启动, 目标点为"击败吾等荣光", 请确保击杀了人偶. 注意第一次跳人偶可能无法点亮哈肯, 需要手动操作.
- 基本流程为: 跳跃-左上角一牛-**回家休息(可选)**-右边两牛-跳跃. 要想关闭途中的回家休息, 请关闭"**启用旅店休息**".
- 低配阵容推荐: 4人队伍.
 	- 2战士, 160+回避, 300+攻击, +20角鹫之剑, 只释放全力一击.
	- 1牧师, 速度最慢, 闪避能堆多高堆多高, **站前排**, 只是放卡恩停欧斯.
 	- 1法师/1牧师, 速度最快, 魔力能堆多高堆多高, **站牧师后面**, 释放LA系魔法或秘术.
	- 技能启用: 关闭系统自动战斗, 勾选"群体控制","强力单体"以及"全体AOE".
	- 推荐勾选'跳过**开箱**后恢复', "启用旅店休息".
	- 参考阵容: 战士面具左上, 牧师叶卡中上, 战士王女右上, 睡法中下.
	- 变种阵容: 牧师面具左上, 战士艾莉赛中上, 战士王女右上, 牧师叶卡中下.
		- 利用牧师叶卡的秘术来充当法师的AOE, 有艾莉赛光环, 伤害充足.
		- 艾莉赛站叶卡前面, 需要堆闪避. 但是因为双光环, 伤害充足.
#### 沙影洞:
- 该任务的休息旅店为要塞, 请确保要塞可见.
- 不推荐在没有完成2周目的情况下使用脚本.
- 需要在完成了2周目后, 从boss房间处获取知识以了解如何关闭陷阱.
- 目前提供了两个版本:
   	- 1F回溯刷金箱. 流程为 回溯->双忍者->三个金箱子->其他箱子. 注意该版本需要**通关2周目且获得解除陷阱的知识**.
   	- 刷怪. 能穿过7个怪物的路线, 平均一次副本能触发5次左右战斗.
#### 贸易水路-船舱2层:
- 确保船1上半部分的地图全部点亮, 船2上半部分的地图全部点亮.
#### 矿石洞: 
- 土洞目前只有一个目标点. 打了就会回城.
- 确保火洞第一个大方块区域内全部点亮. 尤其是大方块的左下角部分.
- 确保光洞第一个大方块区域内全部点亮. 尤其是大方块中部区域.
- 土洞 火洞 风洞会**强制自动战斗**.
#### "击退敌势力"任务: 
- 不包括时间跳跃, 不包括探索地图, 不包括接取任务的部分.
- 旅店休息间隔控制在一次栈桥之行中, 会重复执行几次"击杀前2波"的操作之后再回城. 例如, 如果休息间隔=2, 那么会重复2轮, 一共2x2=4次战斗和4次aoe释放.
- 请确保第七区的地图全部点亮.
- 尽量确保法师是第一速且能一波a掉所有怪物, 不然脚本会有较低的风险卡死.
#### "角鹫之剑"任务: 
- 面板**仅能控制最后的boss战**, 路上小怪为**强制自动战斗**. 流程中不包含回城, 所以量力而行.
- 请确保某些地图中某些区域的全部开启.
- 第一个陷阱前有一定概率出现各种问题导致卡死. *(暂时不会修复!)*
- 开第三层的哈肯有一定概率失败, 并导致角色死亡.*(暂时不会修复!)*

## 如何反馈信息?
- 发送log.txt.
- 发送exe旁边的screenshotwhenrestart文件夹中的截图.
- 发送游戏内地图与画面的截图.

## 我有一个点子/我想要贡献代码
感谢你对于本项目的支持! 但首先, 请访问wiki来了解更多信息.
